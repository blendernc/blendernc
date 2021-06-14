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
        if total:
            times = np.array([item for key, item in self.timestamps.items()]).ravel()
            print("-" * len(titles))
            total_text = "| Total = "
            total_t = "{:.2e} seconds |".format(max(times) - min(times))
            print(
                "{}{}{}".format(
                    total_text,
                    " " * (len(titles) - len(total_text) - len(total_t)),
                    total_t,
                )
            )
            FPS_text = "| FPS = "
            FPS = "{:.2g} |".format(1 / (max(times) - min(times)))
            print(
                "{}{}{}".format(
                    FPS_text, " " * (len(titles) - len(FPS_text) - len(FPS)), FPS
                )
            )
            Frame_text = "| Frame = "
            Frame = "{} |".format(frame)
            print(
                "{}{}{}".format(
                    Frame_text,
                    " " * (len(titles) - len(Frame_text) - len(Frame)),
                    Frame,
                )
            )
            print("-" * len(titles) + "\n")
