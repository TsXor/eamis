from . import fix_cert

from typing import cast, Iterable, Optional
from dataclasses import dataclass
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup, Tag
from nku_sso import BrowserMimic, NKUIAMAuth
from .call_js import js_eval_data_reload
from .dtypes import LessonData, StdCount, ElectResultData
from .interceptor import ConcatenateAuth, PathRateLimit
from .utils import with_validate

# 预定义的限频规则，可在用户代码内更改
BASIC_RATELIMITS = {
    '/eams/stdElectCourse.action': PathRateLimit.Rule({
        '/eams/stdElectCourse.action': 0.5,
    }),
    '/eams/stdElectCourse!defaultPage.action': PathRateLimit.Rule({
        '/eams/stdElectCourse!defaultPage.action': 0.5,
        '/eams/stdElectCourse!data.action': 0.5,
    }),
}

try:
    from .webview_auth import login as webview_login
    WEBVIEW_SUPPORTED = True
except ImportError:
    WEBVIEW_SUPPORTED = False

class EamisJsDataError(Exception):
    def __init__(self, js_code: str) -> None:
        super().__init__()
        self.js_code = js_code

class EamisSoupError(Exception):
    def __init__(self, raw: str) -> None:
        super().__init__()
        self.raw = raw

class EamisHtmlError(Exception):
    def __init__(self, soup: BeautifulSoup) -> None:
        super().__init__()
        self.soup = soup

def load_js(code: str, varname: str, setup: str = ''):
    try:
        return js_eval_data_reload(code, varname, setup)
    except Exception as exc:
        raise EamisJsDataError(code) from exc

def parse_html(raw: str):
    try:
        return BeautifulSoup(raw, features="lxml")
    except Exception as exc:
        raise EamisSoupError(raw) from exc


@dataclass
class ElectProfile:
    id: str
    title: str
    tips: str

@dataclass
class FullData:
    semester_id: str
    sections: list[tuple[ElectProfile, list[LessonData]]]
    std_count: dict[str, StdCount]

@dataclass
class ElectResult:
    data: ElectResultData
    msg: Optional[str]


class EamisClient(BrowserMimic):
    '''
    注意：eamis引入了限频机制，调用某些API间隔过短会导致服务端只回复“不要过快点击”。
    大多数场景下建议通过`limit_rules`增加限频规则来适应eamis。
    在某些重要情况下（例如最终选课请求）可手动插入sleep。
    '''
    limit_rules: dict[str, PathRateLimit.Rule]

    @classmethod
    def domain(cls) -> str: return 'eamis.nankai.edu.cn'

    def __init__(self):
        super().__init__()
        limitor = PathRateLimit(self.domain())
        self.limit_rules = limitor.rules
        self.sess.auth = ConcatenateAuth(limitor)
        self.limit_rules.update(BASIC_RATELIMITS)

    if WEBVIEW_SUPPORTED:
        @classmethod
        def from_webview(cls):
            obj = cls()
            while True:
                webview_login(obj.cookies)
                if not obj.cookies: raise ValueError('登录过程被打断')
                # 注：此处访问任何一个子页面都可以验证是否成功登录
                if obj.activate(): break
                obj.cookies.clear()
            return obj

    @classmethod
    def from_account(cls, user: str, password: str):
        obj = cls()
        auths = cast(ConcatenateAuth, obj.sess.auth)
        auths.children.append(NKUIAMAuth(user, password))
        obj.std_elect_course() # 触发认证
        if not obj.activate(): raise RuntimeError('未知错误，激活未成功')
        return obj

    def activate(self):
        '''
        你需要首先调用这个函数来访问选课主界面，
        否则对任何选课界面的访问都会造成服务端错误。
        为什么呢？要问就问eamis开发人员吧。

        返回值指示登录是否成功。
        '''
        resp = self.document('/eams/stdElectCourse.action', allow_redirects=False)
        return not resp.is_redirect

    def std_elect_course(self):
        resp = self.document('/eams/stdElectCourse.action')
        return resp.text

    def default_page(self, profile_id: str):
        '''
        在获取某个选课页的信息之前，你需要访问这个页面，
        否则对任何选课界面的访问都会造成服务端500错误。
        为什么呢？要问就问eamis开发人员吧。
        '''
        # 根据报错信息来看，这应该与eamis新加入的限制措施有关。
        # eamis现在不允许学生同时打开多个选课页，我盲猜这是通过在这个页面上设置限制得到的。
        resp = self.document(
            '/eams/stdElectCourse!defaultPage.action',
            params={'electionProfile.id': profile_id}
        )
        return resp.text

    def elect_profiles(self) -> Iterable[ElectProfile]:
        soup = parse_html(self.std_elect_course())
        try:
            container = soup.select_one('.ajax_container')
            if not container: raise ValueError('页面加载错误')
            is_notice = lambda e: isinstance(e, Tag) \
                and e.get('id', '').startswith('electIndexNotice') # type: ignore
            for notice in filter(is_notice, container.children):
                title, tips, entry, *_ = filter(lambda e: e.name == 'div', notice.children) # type: ignore
                title_text = title.find('h3').text
                tips_text = tips.find('div').text
                entry_url = entry.find('a')['href']
                entry_url_query = urlparse(self.url(entry_url)).query
                profile_id = parse_qs(entry_url_query)['electionProfile.id'][0]
                yield ElectProfile(profile_id, title_text, tips_text)
        except Exception as exc:
            raise EamisHtmlError(soup) from exc

    def semester_id(self, profile_id: str):
        '''注：这个函数会使用default_page。'''
        soup = parse_html(self.default_page(profile_id))
        try:
            qr_script_url: str = soup.find(id="qr_script")['src'] # type: ignore
            url_query = urlparse(qr_script_url).query
            return parse_qs(url_query)['semesterId'][0]
        except Exception as exc:
            raise EamisHtmlError(soup) from exc

    @with_validate(dict[str, StdCount])
    def std_count(self, semester_id: str):
        resp = self.document(
            '/eams/stdElectCourse!queryStdCount.action',
            params={'projectId': '1', 'semesterId': semester_id}
        )
        return load_js(resp.text, 'window.lessonId2Counts')

    @with_validate(list[LessonData])
    def lesson_data(self, profile_id: str):
        resp = self.document(
            '/eams/stdElectCourse!data.action',
            params={'profileId': profile_id}
        )
        return load_js(resp.text, 'lessonJSONs')

    def full_data(self):
        sections: list[tuple[ElectProfile, list[LessonData]]] = []
        for prof in self.elect_profiles():
            semester_id = self.semester_id(prof.id)
            sections.append((prof, self.lesson_data(prof.id)))
        std_count = self.std_count(semester_id)
        return FullData(semester_id, sections, std_count)

    def elect_course(self, profile_id: str, course_id: int, semester_id: str):
        fetch_headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
        }
        form_data = {
            'optype': 'true',
            'operator0': f'{course_id}:true:0',
            'lesson0': f'{course_id}',
            f'expLessonGroup_{course_id}': 'undefined',
            f'alternateElection_{course_id}': '1'
        }
        resp = self.xhr(
            'POST', '/eams/stdElectCourse!batchOperator.action',
            headers=fetch_headers,
            data=form_data,
            params={'profileId': profile_id},
            cookies={'semester.id': semester_id}
        )
        soup = parse_html(resp.text)
        try:
            msg = soup.select_one('body > table > tr > td > div')
            if msg is not None: msg = msg.text.strip()
            script = soup.select_one('body > table > tr > script')
            if script is None: raise ValueError('返回结果异常')
            data = load_js(
                script.text, 'window.electCourseTable',
                'window.electCourseTable = {'
                    'lessons(id) { Object.assign(this, id); return this; },'
                    'update(elect) { Object.assign(this, elect); return this; }'
                '};'
                'var jQuery = function(selector) { return { html(text) {} }; };'
            )
            data = ElectResultData.model_validate(data)
            return ElectResult(data, msg)
        except Exception as exc:
            raise EamisHtmlError(soup) from exc
