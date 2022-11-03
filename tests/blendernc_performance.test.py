import os
import sys
import time
import unittest
import warnings

import bpy
import dask.array.core as darc
import numpy as np

warnings.simplefilter(action="ignore", category=darc.PerformanceWarning)


def capture_render_log(func):
    def wrapper(*args, **kwargs):
        logfile = "blender_render.log"
        open(logfile, "a").close()
        old = os.dup(1)
        sys.stdout.flush()
        os.close(1)
        os.open(logfile, os.O_WRONLY)
        func(*args, **kwargs)
        os.close(1)
        os.dup(old)

    return wrapper


@capture_render_log
def render_image(var):
    bpy.context.scene.blendernc_datacube_vars = var


class Test_format_import(unittest.TestCase):
    def test_performance_ssh(self):
        file = os.path.abspath("./dataset/ssh_1995-01.nc")
        var = "adt"
        res = 100
        samples = 100
        times = np.zeros(samples)
        for n in range(samples):
            bpy.ops.wm.read_homefile()
            bpy.context.scene.blendernc_file = file
            bpy.context.scene.blendernc_resolution = res
            tic = time.time()
            render_image(var)
            toc = time.time()
            times[n] = toc - tic

        print("[", end="")
        for tt in times:
            print(str(tt) + ",", end="")
        print("]", end="\n")
        # Frames must be more than 2
        self.assertGreater(1 / np.mean(times), 2)

    def test_performance_t2m(self):
        file = os.path.abspath("./dataset/ECMWF_data.grib")
        var = "t2m"
        res = 100
        samples = 100
        times = np.zeros(samples)
        for n in range(samples):
            bpy.ops.wm.read_homefile()
            bpy.context.scene.blendernc_file = file
            bpy.context.scene.blendernc_resolution = res
            tic = time.time()
            render_image(var)
            toc = time.time()
            times[n] = toc - tic

        print("[", end="")
        for tt in times:
            print(str(tt) + ",", end="")
        print("]", end="\n")
        # Frames must be more than 5
        self.assertGreater(1 / np.mean(times), 5)


suite = unittest.defaultTestLoader.loadTestsFromTestCase(Test_format_import)
test = unittest.TextTestRunner().run(suite)

ret = not test.wasSuccessful()
sys.exit(ret)


# # To plot
# data = times
# fig, axs = plt.subplots(3,figsize=(4,4),dpi=200,sharex=True)
# axs[0].plot(x,data,'--k',label='Old load ADT (0.25 deg res)',alpha=0.3)
# axs[0].plot([x[0],x[-1]],[data[0],data[-1]],'--k')
# axs[0].set_ylabel('Load time (s)')
# axs[0].grid()
# round_value = np.round(1/np.asarray(data),1)
# axs[1].plot(x,round_value,'--k',label='Old load ADT (0.25 deg res)',alpha=0.3)
# axs[1].plot([x[0],x[-1]],[1/np.asarray(data)[0],1/np.asarray(data)[-1]],'--k')
# axs[1].set_ylabel('FPS')
# axs[1].grid()

# axs[2].plot(x,np.asarray(data)/np.asarray(data),'--r',alpha=0.3)
# mean = np.mean(np.asarray(data)/np.asarray(data))
# axs[2].plot([x[0],x[0-1]],[mean,mean],'-r')
# axs[2].set_xlabel('iter (n)')
# axs[2].set_ylabel('Ratio (old/new)')
# axs[2].grid()

# plt.show()
# plt.close()
