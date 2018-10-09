import os
from concurrent.futures import ThreadPoolExecutor
import warnings

import requests


from .utils import safe_filename, get_current_time_str
from .utils.mail import Mail


def create_session(pool_connections=10, pool_maxsize=10, max_retries=0):
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=pool_connections,
                                            pool_maxsize=pool_maxsize,
                                            max_retries=max_retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session


class Downloader():

    def __init__(self, worker=None):
        worker = worker or 8
        self.session = create_session(pool_maxsize=worker, pool_connections=worker, max_retries=3)
        self.worker = worker

    def download_image(self, image_url, output, timeout=30):
        if os.path.exists(output) and os.path.getsize(output) != 0:
            warnings.warn('图片已存在, pass', output)
            return output
        response = self.session.get(image_url, timeout=timeout)
        if response.status_code == 200:
            with open(output, 'wb') as f:
                f.write(response.content)
                return output

    def download_images(self, image_urls, output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        with ThreadPoolExecutor(max_workers=self.worker) as executor:
            for idx, image_url in enumerate(image_urls, start=1):
                ext = self.find_suffix(image_url)
                filename = '{}.{}'.format(str(idx), ext)
                pic_path = os.path.join(output_dir, filename)
                executor.submit(self.download_image,
                                image_url=image_url,
                                output=pic_path,
                                timeout=10)

    def find_suffix(self, image_url, default='jpg', allow=frozenset(['jpg', 'png', 'jpeg', 'gif'])):
        """从图片url提取图片扩展名
        :param image_url: 图片链接
        :param default: 扩展名不在 allow 内，则返回默认扩展名
        :param allow: 允许的扩展名
        :return ext: 扩展名，不包含.
        """
        ext = image_url.rsplit('.', 1)[-1].lower()
        if ext not in allow:
            return default
        return ext

    def download_chapter(self, chapter, output_dir, is_generate_pdf, is_send_email):
        """下载整个章节的图片，按漫画名按章节保存
        :param <Chapter instance> chapter : Chapter instance
        :param str output_dir: 图片保存目录
        :param boolean is_generate_pdf: 是否生成pdf
        :return tuple (str chapter_dir, str pdf_path): 当前章节漫画目录，pdf文件路径
        """

        site_name = safe_filename(chapter.site_name)
        comic_title = safe_filename(chapter.comic_title)
        chapter_pics = chapter.chapter_pics

        if chapter.chapter_number:
            chapter_title = '第{}话 {}'.format(chapter.chapter_number, chapter.chapter_title)
        else:
            chapter_title = chapter.chapter_title
        chapter_title = safe_filename(chapter_title)

        chapter_dir = os.path.join(output_dir, site_name, comic_title, chapter_title)

        if not os.path.exists(chapter_dir):
            os.makedirs(chapter_dir)

        print('{} 正在下载: {}'.format(get_current_time_str(), chapter_title))
        self.download_images(chapter_pics, chapter_dir)

        if is_generate_pdf or is_send_email:
            from .utils.img2pdf import image_dir_to_pdf
            pdf_dir = os.path.join(output_dir, site_name, 'pdf - {}'.format(comic_title))
            pdf_name = '{} {}.pdf'.format(comic_title, chapter_title)
            pdf_path = os.path.join(pdf_dir, pdf_name)
            if not os.path.exists(pdf_dir):
                os.makedirs(pdf_dir)
            image_dir_to_pdf(img_dir=chapter_dir,
                             output=pdf_path,
                             sort_by=lambda x: int(x.split('.')[0]))
            if is_send_email:
                Mail.send(subject=pdf_name,
                          content=None,
                          file_list=[pdf_path, ])

        else:
            pdf_path = None
        return chapter_dir, pdf_path