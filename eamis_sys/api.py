from . import fix_cert

from typing import Iterable, Optional
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup, Tag
from nku_sso import BrowserMimic, NKUIAMAuth
from .call_js import js_eval_data_reload
from .dtypes import LessonData, StdCount, ElectResultData
from .utils import with_validate

try:
    from .webview_auth import login as webview_login
    WEBVIEW_SUPPORTED = True
except ImportError:
    WEBVIEW_SUPPORTED = False

class EamisJsDataError(Exception):
    js_code: str

    def __init__(self, js_code: str, *args: object) -> None:
        super().__init__(*args)
        self.js_code = js_code

def load_js(code: str, varname: str, setup: str = ''):
    try:
        return js_eval_data_reload(code, varname, setup)
    except Exception as exc:
        raise EamisJsDataError(code) from exc


class EamisClient(BrowserMimic):
    '''
    注意：连续调用某些API时需要在中间插入sleep，否则服务端只会回复“不要过快点击”。
    '''

    @classmethod
    def domain(cls) -> str: return 'eamis.nankai.edu.cn'

    def __init__(self):
        super().__init__()

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
        obj.sess.auth = NKUIAMAuth(user, password)
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

    def elect_profiles(self) -> Iterable[tuple[str, str, str]]:
        soup = BeautifulSoup(self.std_elect_course(), features="lxml")
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
            yield title_text, tips_text, profile_id 

    def semester_id(self, profile_id: str):
        '''注：这个函数会使用default_page。'''
        soup = BeautifulSoup(self.default_page(profile_id), features="lxml")
        qr_script_url: str = soup.find(id="qr_script")['src'] # type: ignore
        url_query = urlparse(qr_script_url).query
        return parse_qs(url_query)['semesterId'][0]

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

    def all_lesson_data(self):
        lesson_data: dict[str, list[LessonData]] = {}
        for title, tips, profile_id in self.elect_profiles():
            semester_id = self.semester_id(profile_id)
            lesson_data[profile_id] = self.lesson_data(profile_id)
        std_count = self.std_count(semester_id)
        return lesson_data, std_count

    class ElectResult:
        raw: str
        data: Optional[ElectResultData] = None
        msg: Optional[str] = None

        def __init__(self, text: str):
            self.raw = text
            try:
                soup = BeautifulSoup(self.raw, features="lxml")
                msg = soup.select_one('body > table > tr > td > div')
                if msg is not None:
                    self.msg = msg.text.strip()
                script = soup.select_one('body > table > tr > script')
                if script is not None:
                    data = load_js(
                        script.text, 'window.electCourseTable',
                        'window.electCourseTable = {'
                            'lessons(id) { Object.assign(this, id); return this; },'
                            'update(elect) { Object.assign(this, elect); return this; }'
                        '};'
                        'var jQuery = function(selector) { return { html(text) {} }; };'
                    )
                    self.data = ElectResultData.model_validate(data)
            except: pass

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
        return self.ElectResult(resp.text)
