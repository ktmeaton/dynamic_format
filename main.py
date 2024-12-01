#!/usr/bin/env python3

from datetime import datetime
import time
import re
import copy
import subprocess
import asyncio
import logging
import os
import shutil
import sys
from enum import Enum

from io import StringIO
from contextlib import redirect_stdout, redirect_stderr

import yaml
#from rich import print
from rich.align import Align
from rich.console import Console
from rich.progress import Progress, TextColumn, MofNCompleteColumn, BarColumn, TimeRemainingColumn
from rich.layout import Layout
from rich.logging import RichHandler
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.tree import Tree


def get_cli_options():
    import argparse

    description = 'Description goes here!.'
    parser = argparse.ArgumentParser(description=description)

    #parser.add_argument('--display', help=f"Display mode. (default: {Display(None)})", type=Display.argparse, choices=list(Display), default=Display(None))
    parser.add_argument('-w', '--workflow', help="Workflow YAML file", required=True)
    parser.add_argument('--unsafe', help="Enabled unsafe mode", dest="safe", action="store_false")
    return parser.parse_args()

class TaskStatus(Enum):
    PENDING = 1
    RUNNING = 2
    COMPLETE = 3

    def __repr__(self):
        return str(self)

class TaskResult(Enum):
    UNKNOWN = 1
    PASS = 2
    FAIL = 3

    def __repr__(self):
        return str(self)

class Task:

    def __init__(self, name:str, data:dict, safe:bool=True):
        self.name = name
        self.safe = safe
        self.data = data
        self.status = TaskStatus.PENDING
        self.result = TaskResult.UNKNOWN
        self.stdout = None
        self.stderr = None
        self.output = None
        self.error = None
        self.return_code = None

    def fn(self):
        """
        Create a dynamic function from the run data
        """

        fn_content = "return 0"

        if "run" in self.data:
            run_data = self.data["run"]

            # Option 1. Shell Command
            if type(run_data) == str:
                lines = [l.strip() for l in run_data.split("\n") if l != ""]
                fn_lines = ["import subprocess"]
                for line in lines:
                    command = [word for word in line.split(" ") if word != ""]
                    fn_line = f"subprocess.run({command})"
                    fn_lines.append(fn_line)
                fn_content = ";".join(fn_lines)
            elif type(run_data) == dict and "function" in run_data:
                fn_content = run_data["function"]

        return fn_content


    async def run(self, pass_codes=[0]):
        g = {"__builtins__": {}} if self.safe else {}

        cmd = "echo test > test.txt"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE)

        stdout, stderr = await proc.communicate()
        self.return_code = proc.returncode
        if stdout:
            self.stdout = stdout.decode().strip()
        if stderr:
            self.stderr = stderr.decode().strip()

        self.status = TaskStatus.COMPLETE

        if self.return_code == 0:
            self.result = TaskResult.PASS
        else:
            self.result = TaskResult.FAIL
        # stdout = StringIO()
        # stderr = StringIO()
        # output = None

        # with redirect_stdout(stdout):
        #     with redirect_stderr(stderr):
        #         try:
        #             fn_content = self.fn()
        #             #exec(f"def fn(): return({fn_content})", g, locals())
        #             exec(f"def fn(): {fn_content}", g, locals())
        #             self.output = locals()["fn"]()
        #             self.result = TaskResult.PASS
        #             print(stdout.getvalue())
        #         except Exception as e:
        #             result = TaskResult.FAIL
        #             self.error = str(e)
        #             self.result = TaskResult.FAIL

        # self.stdout = stdout.getvalue().strip()
        # self.stderr = stderr.getvalue().strip()
        # self.status = TaskStatus.COMPLETE


    def summary(self):
        msg = self.name
        if self.status in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            msg += f" | status: {self.status.name}"
        elif self.status == TaskStatus.COMPLETE:
            msg += f" | result: {self.result.name} | return_code: {self.return_code}"
            if self.result == TaskResult.FAIL:
                msg += f" | error: {self.error}"
            elif self.result == TaskResult.PASS:
                msg += f" | stdout: {self.stdout}"
        return msg

    def __repr__(self):
        return self.name

class ConsolePanel(Console):
    def __init__(self,*args,**kwargs):
        console_file = open(os.devnull,'w')
        super().__init__(record=True,file=console_file,*args,**kwargs)

    def __rich_console__(self,console,options):
        texts = self.export_text(clear=False).split('\n')
        for line in texts[-options.height:]:
            yield line

class Gui():

    def __init__(self):
        self.padding = (2,2)
        self.border_style = "white"
        self.layout = Layout(name="root")

        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=2),
            Layout(name="log", ratio=1),
        )
        self.layout["main"].split_row(
            Layout(name="tree", ratio=1),
            Layout(name="progress", ratio=2),
            Layout(name="something", ratio=2),
        )

        # Header
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="right")
        grid.add_row(
            "[b]Dynamic Format[/b] Layout application",
            datetime.now().ctime().replace(":", "[blink]:[/]"),
        )
        self.header = Panel(grid, style="white on blue")
        self.layout["header"].update(self.header)


        # Progress
        self.layout["progress"].split(
            Layout(name="progress_summary", size=3),
            Layout(name="progress_jobs")
        )
        self.overall_progress = Progress(TextColumn("{task.completed}"))
        self.overall_progress.add_task("completed", total=0)
        self.pass_progress = Progress(TextColumn("[green]{task.completed}"))
        self.pass_progress.add_task("pass", total=0)
        self.fail_progress = Progress(TextColumn("[red]{task.completed}"))
        self.fail_progress.add_task("fail", total=0)
        self.running_progress = Progress(TextColumn("[blue]{task.completed}"))
        self.running_progress.add_task("run", total=0)

        progress_summary = []
        for title,renderable in zip(
            ["Complete", "Pass", "Fail", "Running"],
            [self.overall_progress, self.pass_progress, self.fail_progress, self.running_progress]
            ):
            progress_summary.append(
                Panel(
                    Align(renderable, align="center"),
                    title=title,
                    border_style=self.border_style,
                    padding=(0,0),
                )
            )
        self.layout["progress_summary"].split_row(*progress_summary)
        self.progress = Progress(
            TextColumn("{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeRemainingColumn(),
            #MofNCompleteColumn("/"),
            #TextColumn("[yellow]{task.fields[current]}")
        )
        progress_panel = Panel(
            self.progress,
            title="Progress",
            border_style=self.border_style,
            padding=self.padding,
        )
        self.layout["progress_jobs"].update(progress_panel)


        # Task Tree
        self.tree = Tree("Tasks")
        tree_panel = Panel(
            self.tree,
            title="Active Tasks",
            border_style=self.border_style,
            padding=self.padding,
        )
        self.layout["tree"].update(tree_panel)
        for task in self.progress.tasks:
            self.tree.add(task.description)

        # Log
        self.log = ConsolePanel()
        log_panel = Panel(
            self.log,
            title="Log",
            border_style=self.border_style,
            padding=(0,0), 
        )
        self.layout["log"].update(log_panel)


def dynamic_format(data, vars:dict, allow_missing=True, parent=None):
    if type(data) == dict:
        for k,v in data.items():
            v_data, vars = dynamic_format(v, vars, allow_missing, parent=k)
            data[k] = v_data
    elif type(data) == list:
        for i,v in enumerate(data):
            v_data, vars = dynamic_format(v, vars, allow_missing, parent=parent)
            data[i] = v_data
    else:
        data = str(data)
        format_dict = {}
        regex = "(?<!{{)(?<={)[A-Za-z0-9_]+(?=})(?!}})"
        for match in re.finditer(regex, data):
            var = match.group()
            format_dict[var] = vars[var] if var in vars else f"{{{var}}}"
            if not allow_missing:
                raise Exception(f"Undefined format variable `{var}` in {parent} = {data}")
        data = data.format(**format_dict)
    return (data, vars)

def dynamic_step(data:dict):
    variables = data["variables"] if "variables" in data else {}
    data = [data]
    for k,v in variables.items():
        if type(v) == dict: continue
        elif type(v) != list:
            try:
                v = eval(v)
                v = [v] if type(v) != list else v
            except:
                v = [v]
        values = v

        data_expanded = []
        for d in data:
            for v in values:
                exec(f"{k} = '{v}'")
                v_data = copy.deepcopy(d)
                dynamic_format(v_data, locals())
                data_expanded.append(v_data)

        data = data_expanded

    # Final pass, make sure no missing var?
    for i,d in enumerate(data):
        dynamic_format(d, locals(), allow_missing=False)
        data[i] = d

    return data


async def main(workflow:str, safe:bool=True):
    workflow_path = workflow
    with open(workflow) as infile:
        workflow = yaml.safe_load(infile)
    del infile
    gui = Gui()

    #loop = asyncio.new_event_loop()

    with Live(gui.layout, refresh_per_second=10, screen=True):
        gui.log.print(f"[WORKFLOW] Running: {workflow_path}")
        for job,job_data in workflow["jobs"].items():
            gui.log.print(f"[JOB] Running: {job}")
            job_tree = gui.tree.add(job)
            steps = job_data["steps"] if job_data != None and "steps" in job_data and job_data["steps"] != None else {}
            num_steps = len(steps)
            job_progress = gui.progress.add_task(f"[red]{job}", total=num_steps, current="")

            if num_steps == 0:
                progress.update(job_progress, advance=1)
                continue
            for step,step_data in steps.items():
                gui.log.print(f"[STEP] Running: {step}")
                step_tree = job_tree.add(step)
                tasks = dynamic_step(step_data)
                step_progress = gui.progress.add_task(f"    [red]{step}", total=len(tasks), current=f"")
                for i,task_data in enumerate(tasks):
                    task = Task(name=f"{job}.{step}.{i}", data=task_data, safe=safe)
                    gui.overall_progress._tasks[0].total += 1
                    #task_short = str(task)[0:100] + "..." if len(str(task)) > 100 else str(task)
                    #gui.log.print(f"[TASK] Dispatching: {task_short}")
                    current = ""
                    fn_def = "async def fn(): None"
                    args = {}
                    # # Option 1. Function
                    # if "function" in task:
                    #     args = task["args"] if "args" in task else {}
                    #     fn_def = "async def fn({args}): {f}".format(
                    #         args=",".join([k for k in args]),
                    #         f = task['function']
                    #     )                          
                    #     if len(args) > 0:
                    #         current = " ".join([f"{k}={v}" for k,v in args.items()])
                    #     else:
                    #         current = task['function']
                    #     current = f"\[{current}]"
                    # elif "command" in task:
                    #     command = [word for word in task["command"].split(" ") if word != ""]
                    #     fn_def = "async def fn(): {f}".format(
                    #         f=f"subprocess.run({command}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)"
                    #     )
                    #     args = {}
                    #     current = f"\[{task['command']}]"

                    gui.log.print(f"[TASK] {task}")
                    await task.run()
                    time.sleep(1)
                    gui.log.print(f"[TASK] {task.summary()}", soft_wrap=False)
                    #exec(fn_def, {}, {})  
                    #await fn(**args)

                    task_tree = step_tree.add(current)
                    time.sleep(0.05)

                    # When we know task is complete
                    step_tree.children = [c for c in step_tree.children if c != task_tree]
                    gui.progress.update(step_progress, advance=1, current=current)
                    gui.overall_progress.update(0, advance=1)
                job_tree.children = [c for c in job_tree.children if c != step_tree]
                gui.log.print(f"[STEP] Completed: {step}")

            gui.tree.children = [c for c in gui.tree.children if c != job_tree]
            gui.progress.update(job_progress, advance=1)

            gui.log.print(f"[JOB] Completed: {job}")

        while not gui.progress.finished:
            for task in gui.progress.tasks:
                if task.completed:
                    task.visible = False
            #completed = sum(task.completed for task in gui.progress.tasks)
            #gui.progress.update(0, completed=completed)
            #gui.log.print(f"[WORKFLOW] Completed: {completed}")
        while True:
            ...


if __name__ == "__main__":

    options = get_cli_options()
    kwargs = vars(options)
    asyncio.run(main(**kwargs))
