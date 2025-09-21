
import os
import subprocess
import sys

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildExecutable(build_py):
    def run(self):
        """Run PyInstaller to build the executable before the actual build process"""
        args = [
            sys.executable,
            "-m",
            "PyInstaller",
            "--windowed",
            "--noconfirm",
            "--onedir",
            "--clean",
            "--name=seismicfilter",
            "--hidden-import=wx._xml",
            "--hidden-import=pandas._libs.tslibs.timedeltas",
            "--hidden-import=openpyxl"
        ]
        if sys.platform != "win32":
            args.append("--strip")
            args.append("--icon=icons/logo.png")
        else:
            args.append("--icon=icons/logo.ico")
        args.append("__main__.py")
        os.environ["PYTHONOPTIMIZE"] = "2"
        subprocess.run(
            args, check=True, env=os.environ
        )  # Create a single executable file  # Name of the output file  # Your main script
        super().run()


setup(name="geomech", cmdclass={"build_py": BuildExecutable})  # Replace with actual package name
