import time
from .api import EamisClient
from .dtypes import LessonData


class EamisCatcher(EamisClient):
    @staticmethod
    def format_lesson_name(lesson: LessonData):
        # 课程序号--课程名称(课程代码)--授课教师--授课校区
        time_str = ', '.join(f'{arr.weekStateDigest}周{arr.startUnit}-{arr.endUnit}节' for arr in lesson.arrangeInfo)
        return f'{lesson.no}--{lesson.name}({lesson.code})--{lesson.teachers}--{lesson.campusName}--<{time_str}>'

    @staticmethod
    def lesson_list_to_num_map(lessons: list[LessonData]):
        result_dic: dict[str, LessonData] = {}
        for lesson in lessons:
            result_dic[lesson.no] = lesson
        return result_dic

    def prepare_id(self, lesson_plan: dict[str, list[str]]):
        prepared_map: dict[str, tuple[str, list[int]]] = {}
        info_map: dict[str, list[LessonData]] = {}
        for profile_id, lesson_num_list in lesson_plan.items():
            semester_id = self.semester_id(profile_id)
            lesson_data = self.lesson_data(profile_id)
            lesson_num_map = self.lesson_list_to_num_map(lesson_data)
            prepared_map[profile_id] = (semester_id, [lesson_num_map[lesson_num].id for lesson_num in lesson_num_list])
            info_map[profile_id] = lesson_data
            time.sleep(0.5) # 防止触发“不要过快点击”
        return prepared_map, info_map

    def speed_catch(self, prepared_map: dict[str, tuple[str, list[int]]], humanly_interval=0.5):
        speed_results: list[tuple[str, int, str]] = []
        for lesson_section, (semester_id, lesson_id_list) in prepared_map.items():
            for lesson_id in lesson_id_list:
                time.sleep(humanly_interval)
                result_text = self.elect_course(lesson_section, lesson_id, semester_id)
                speed_results.append((lesson_section, lesson_id, result_text.raw))
        return speed_results
