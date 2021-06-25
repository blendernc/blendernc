#!/usr/bin/env python3
import time

import numpy as np

# TODO: Add debug - logger option as a setting of the Add-On


class Timer:
    def __init__(self):
        self.timestamps = {}
        self.nolabel = []
        self.tmp = []

    def tick(self, label=""):
        if label == "":
            self.nolabel.append(time.time())
            self.timestamps[label] = self.nolabel
        else:
            self.tmp.append(time.time())
            self.timestamps[label] = self.tmp
            if len(self.timestamps[label]) == 2:

                self.tmp = []

    def print_spaces(self, text_1, text_2, total_space=30):
        empty_space = " " * (total_space - len(text_1) - len(text_2))
        print("{}{}{}".format(text_1, empty_space, text_2))

    def report(self, total=False, frame=None):
        titles = ""
        times = ""
        for key, item in self.timestamps.items():
            if key != "":
                titles += "| {} |".format(key)
                time_elapsed_s = "{:.2e}".format(item[1] - item[0])
                spaceL = " " * (len(key) - len(time_elapsed_s))
                times += "| {}{} |".format(spaceL, time_elapsed_s)
        print("-" * len(titles))
        print(titles)
        print(times)
        title_length = len(titles)
        if total:
            times = np.array([item for key, item in self.timestamps.items()]).ravel()
            print("-" * title_length)
            total_text = "| Total = "
            total_t = "{:.2e} seconds |".format(max(times) - min(times))
            self.print_spaces(total_text, total_t, title_length)
            FPS_text = "| FPS = "
            FPS = "{:.2g} |".format(1 / (max(times) - min(times)))
            self.print_spaces(FPS_text, FPS, title_length)
            Frame_text = "| Frame = "
            Frame = "{} |".format(frame)
            self.print_spaces(Frame_text, Frame, title_length)
            print("-" * len(titles) + "\n")
