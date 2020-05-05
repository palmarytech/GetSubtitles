# coding: utf-8

import json
import re
from contextlib import closing
from collections import OrderedDict as order_dict

import requests
from bs4 import BeautifulSoup

from getsub.downloader.downloader import Downloader
from getsub.util import ProgressBar


""" SubHD Downloader
"""


class SubHDDownloader(Downloader):

    name = "subhd"
    choice_prefix = "[SUBHD]"
    site_url = "http://subhd.la"
    search_url = "http://subhd.la/search/"

    def get_subtitles(self, video, sub_num=5):

        print("Searching SUBHD...", end="\r")

        keywords = Downloader.get_keywords(video)
        keyword = " ".join(keywords)

        sub_dict = order_dict()
        s = requests.session()
        s.headers.update(Downloader.header)
        while True:
            r = s.get(SubHDDownloader.search_url + keyword, timeout=10,)
            bs_obj = BeautifulSoup(r.text, "html.parser")
            try:
                small_text = bs_obj.find("small").text
            except AttributeError:
                char_error = "The URI you submitted has disallowed characters"
                if char_error in bs_obj.text:
                    print("[SUBHD ERROR] " + char_error + ": " + keyword)
                    return sub_dict

            if "总共 0 条" not in small_text:

                results = bs_obj.find_all(
                    "div", class_="mb-4 bg-white rounded shadow-sm"
                )

                for one_box in results:

                    if video.info["type"] == "movie" and not one_box.find(
                        "div", class_="px-1 rounded-sm bg-danger text-white"
                    ):
                        # this search result not marked as "movie" in subhd
                        continue

                    a = one_box.find("div", class_="f12 pt-1").find("a")
                    sub_url = SubHDDownloader.site_url + a.attrs["href"]
                    sub_name = SubHDDownloader.choice_prefix + a.text
                    text = one_box.text
                    if "/a" in a.attrs["href"]:
                        type_score = 0
                        type_score += ("英文" in text) * 1
                        type_score += ("繁体" in text) * 2
                        type_score += ("简体" in text) * 4
                        type_score += ("双语" in text) * 8
                        sub_dict[sub_name] = {
                            "lan": type_score,
                            "link": sub_url,
                            "session": None,
                        }
                    if len(sub_dict) >= sub_num:
                        del keywords[:]
                        break

            if len(keywords) > 1:  # not get enough results, continue
                keyword = keyword.replace(keywords[-1], "")
                keywords.pop(-1)
                continue

            break

        if len(sub_dict.items()) > 0 and list(sub_dict.items())[0][1]["lan"] < 8:
            # first candidate is not double language,
            # move the candidate with maximum score to the first
            sub_dict = order_dict(
                sorted(sub_dict.items(), key=lambda e: e[1]["lan"], reverse=True)
            )
        return sub_dict

    def download_file(self, file_name, sub_url, session=None):

        if not session:
            session = requests.session()
            session.headers.update(Downloader.header)

        # enter subtitle page
        r = session.get(sub_url)
        bs_obj = BeautifulSoup(r.text, "html.parser")
        for subtitle in bs_obj.find_all(
            "div", class_="border-top border-light px-3 py-3 clearfix"
        ):
            preview_button = subtitle.find("div", class_="float-right text-secondary").a
            dasid = preview_button.attrs["sid"]
            dafname = preview_button.attrs["data-fname"]
            print(dasid, dafname)
            return

        # NOTE: some pages still support method below and have no preview
        # subtitls, e.g.,http://subhd.la/a/312224

        # TODO

        sid = sub_url.split("/")[-1]
        r = session.get(sub_url)

        dtoken = bs_obj.find("button", {"id": "down"})["dtoken1"]

        r = session.post(
            SubHDDownloader.site_url + "/ajax/down_ajax",
            data={"sub_id": sid, "dtoken1": dtoken},
        )

        content = r.content.decode("unicode-escape")
        if json.loads(content)["success"] is False:
            msg = (
                "download too frequently with subhd downloader,"
                + " please change to other downloaders"
            )
            return None, None, msg
        res = re.search('http:.*(?=")', r.content.decode("unicode-escape"))
        download_link = res.group(0).replace("\\/", "/")
        try:
            with closing(requests.get(download_link, stream=True)) as response:
                chunk_size = 1024  # 单次请求最大值
                # 内容体总大小
                content_size = int(response.headers["content-length"])
                bar = ProgressBar("Get", file_name.strip(), content_size)
                sub_data_bytes = b""
                for data in response.iter_content(chunk_size=chunk_size):
                    sub_data_bytes += data
                    bar.refresh(len(sub_data_bytes))
            # sub_data_bytes = requests.get(download_link, timeout=10).content
        except requests.Timeout:
            return None, None, "false"
        if "rar" in download_link:
            datatype = ".rar"
        elif "zip" in download_link:
            datatype = ".zip"
        elif "7z" in download_link:
            datatype = ".7z"
        else:
            datatype = "Unknown"

        return datatype, sub_data_bytes, ""
