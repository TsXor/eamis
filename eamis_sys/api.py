from typing import cast, Iterable
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup, Tag
from .call_js import js_eval_data_reload
from .webview_auth import webview_login
from .client import EamisClientBasics
from .dtypes import LessonData


class EamisJsDataError(Exception): pass


class EamisClient(EamisClientBasics):
    '''
    注意：连续调用API时需要在中间插入sleep，否则服务端只会回复“不要过快点击”。
    '''

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

    def default_page(self, profile_id: int):
        '''
        在获取某个选课页的信息之前，你需要访问这个页面，
        否则对任何选课界面的访问都会造成服务端500错误。
        为什么呢？要问就问eamis开发人员吧。
        '''
        # 根据报错信息来看，这应该与eamis新加入的限制措施有关。
        # eamis现在不允许学生同时打开多个选课页，我盲猜这是通过在这个页面上设置限制得到的。
        resp = self.document(
            '/eams/stdElectCourse!defaultPage.action',
            params={'electionProfile.id': str(profile_id)}
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
            yield title.find('h3').text, tips.find('div').text, entry.find('a')['href']

    def elect_profile_ids(self):
        for title, tips, entry in self.elect_profiles():
            url_query = urlparse(self.url(entry)).query
            yield int(parse_qs(url_query)['electionProfile.id'][0])

    def semester_id(self, profile_id: int):
        soup = BeautifulSoup(self.default_page(profile_id), features="lxml")
        qr_script_url: str = soup.find(id="qr_script")['src'] # type: ignore
        url_query = urlparse(qr_script_url).query
        return parse_qs(url_query)['semesterId'][0]

    def lesson_data(self, profile_id: int):
        resp = self.document(
            '/eams/stdElectCourse!data.action',
            params={'profileId': str(profile_id)}
        )
        try:
            dat = js_eval_data_reload(resp.text, 'lessonJSONs')
        except Exception:
            raise EamisJsDataError(resp.text)
        return cast(list[LessonData], dat)

    def all_lesson_data(self):
        result: dict[int, list[LessonData]] = {}
        for profile_id in self.elect_profile_ids():
            self.default_page(profile_id)
            result[profile_id] = self.lesson_data(profile_id)
        return result

    def elect_course(self, profile_id: int, course_id: int, semester_id: str):
        fetch_headers = {
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'Origin': f'https://{self.HOST}',
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
            params={'profileId': str(profile_id)},
            cookies={'semester.id': str(semester_id)}
        )
        return resp.text
