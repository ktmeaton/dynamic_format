#!/usr/bin/env python3

from datetime import datetime
import time
import re
import copy
import subprocess
import asyncio
import os
import shutil
import sys
from enum import Enum

from io import StringIO
from contextlib import redirect_stdout, redirect_stderr, nullcontext

import yaml
#from rich import print
from rich.align import Align
from rich.console import Console
from rich.progress import Progress, TextColumn, MofNCompleteColumn, BarColumn, TimeRemainingColumn
from rich.layout import Layout
from rich.panel import Panel
from rich.live import Live
from rich.table import Table
from rich.tree import Tree


class Display(Enum):
    RICH = 1
    TEXTUAL = 2
    TEXT = 3

    def __str__(self):
        return self.name.lower()
    def __repr__(self):
        return str(self)
    @staticmethod
    def argparse(s):
        try:
            return Display[s.upper()]
        except KeyError:
            return s

def get_cli_options():
    import argparse

    description = 'Description goes here!.'
    parser = argparse.ArgumentParser(description=description)

    parser.add_argument('--display', help=f"Display mode. (default: {Display.RICH})", type=Display.argparse, choices=list(Display), default=Display.RICH)
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
        self.command = None

    # def fn(self):
    #     """
    #     Create a dynamic function from the run data
    #     """

    #     fn_content = "return 0"

    #     if "run" in self.data:
    #         run_data = self.data["run"]

    #         # Option 1. Shell Command
    #         if type(run_data) == str:
    #             lines = [l.strip() for l in run_data.split("\n") if l != ""]
    #             fn_lines = ["import subprocess"]
    #             for line in lines:
    #                 command = [word for word in line.split(" ") if word != ""]
    #                 fn_line = f"subprocess.run({command})"
    #                 fn_lines.append(fn_line)
    #             fn_content = ";".join(fn_lines)
    #         elif type(run_data) == dict and "function" in run_data:
    #             fn_content = run_data["function"]

    #     return fn_content

    def command(self):
        """
        Create a dynamic command from the run data
        """

        command = None

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

        self.command = command


    async def run(self, pass_codes=[0]):
        g = {"__builtins__": {}} if self.safe else {}

        cmd = "echo test1 > test.txt; echo test2 >> test.txt"
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

class Workflow():
    def __init__(self, data:dict, display:Display=Display.RICH):
        self.data = data
        if "name" not in self.data:
            raise Exception("Workflow does not have a name.")
        self.name = self.data["name"]
        self.display = display
        self.init_gui()
        self.jobs = self.data["jobs"] if "jobs" in self.data else {}

    def __repr__(self):
        return self.name

    def logging(self, message:str, level:str="INFO", formatter:str="{now}\t[{level}] {message}"):
        message = formatter.format(level=level, message=message, now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if self.display == Display.RICH:
            self.log.print(message)
        else:
            print(message)

    def init_gui(self):
        padding = (2,2)
        border_style = "white"

        self.gui = Layout(name="root")

        # Split the screen vertically into 3
        self.gui.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=2),
            Layout(name="log", ratio=1),
        )
        # Split the main section horizontally into 3
        self.gui["main"].split_row(
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
        header = Panel(grid, style="white on blue")
        self.gui["header"].update(header)

        # Progress
        self.gui["progress"].split(
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
                    border_style=border_style,
                    padding=(0,0),
                )
            )
        self.gui["progress_summary"].split_row(*progress_summary)

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
            border_style=border_style,
            padding=padding,
        )
        self.gui["progress_jobs"].update(progress_panel)


        # Task Tree
        self.tree = Tree("Tasks")
        tree_panel = Panel(
            self.tree,
            title="Active Tasks",
            border_style=border_style,
            padding=padding,
        )
        self.gui["tree"].update(tree_panel)
        for task in self.progress.tasks:
            self.tree.add(task.description)

        # Log
        self.log = ConsolePanel()
        log_panel = Panel(
            self.log,
            title="Log",
            border_style=border_style,
            padding=(0,0), 
        )
        self.gui["log"].update(log_panel)


    def dynamic_format(self, data, vars:dict, allow_missing=True, parent=None):
        if type(data) == dict:
            for k,v in data.items():
                v_data, vars = self.dynamic_format(v, vars, allow_missing, parent=k)
                data[k] = v_data
        elif type(data) == list:
            for i,v in enumerate(data):
                v_data, vars = self.dynamic_format(v, vars, allow_missing, parent=parent)
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

    def dynamic_tasks(self, data:dict):
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
                    self.dynamic_format(v_data, locals())
                    data_expanded.append(v_data)

            data = data_expanded

        # Final pass, make sure no missing var?
        for i,d in enumerate(data):
            self.dynamic_format(d, locals(), allow_missing=False)
            data[i] = d

        return data


async def main(workflow:str, safe:bool=True, display:Display=Display.RICH):
    workflow_path = workflow
    with open(workflow) as infile:
        data = yaml.safe_load(infile)
    workflow = Workflow(data=data, display=display)


    with Live(workflow.gui, refresh_per_second=10, screen=True) if display == Display.RICH else nullcontext():
        workflow.logging(f"Starting workflow: {workflow}", level="INFO")

        # Iterate through jobs
        for job,job_data in workflow.jobs.items():
            workflow.logging(f"Starting job: {job}", level="INFO")
            job_tree = workflow.tree.add(job)
            steps = job_data["steps"] if job_data != None and "steps" in job_data and job_data["steps"] != None else {}
            num_steps = len(steps)
            job_progress = workflow.progress.add_task(f"[red]{job}", total=num_steps, current="")

            if num_steps == 0:
                workflow.progress.update(job_progress, advance=1)
                continue
            for step,step_data in steps.items():
                workflow.logging(f"Starting step: {step}", level="INFO")
                step_tree = job_tree.add(step)
                tasks = workflow.dynamic_tasks(step_data)

                step_progress = workflow.progress.add_task(f"    [red]{step}", total=len(tasks), current=f"")
                for i,task_data in enumerate(tasks):
                    task = Task(name=f"{job}.{step}.{i}", data=task_data, safe=safe)
                    workflow.overall_progress._tasks[0].total += 1
                    current = ""
                    fn_def = "async def fn(): None"
                    args = {}

                    workflow.logging(f"Dispatching task: {task}")
                    await task.run()
                    time.sleep(1)
                    workflow.logging(f"Completed task: {task.summary()}")
                    #exec(fn_def, {}, {})  
                    #await fn(**args)

                    task_tree = step_tree.add(current)
                    #time.sleep(0.05)

                    # When we know task is complete
                    step_tree.children = [c for c in step_tree.children if c != task_tree]
                    workflow.progress.update(step_progress, advance=1, current=current)
                    workflow.overall_progress.update(0, advance=1)
                job_tree.children = [c for c in job_tree.children if c != step_tree]
                workflow.logging(f"Completed step: {step}")

            workflow.tree.children = [c for c in workflow.tree.children if c != job_tree]
            workflow.progress.update(job_progress, advance=1)

            workflow.logging(f"Completed job: {job}")

        # At this point, the workflow has been fully queued
        completed = False
        while not workflow.progress.finished and not completed:
            for task in workflow.progress.tasks:
                if task.completed:
                    task.visible = False
            completed = sum(task.completed for task in workflow.progress.tasks) == len(workflow.progress.tasks)
        workflow.logging(f"Completed workflow: {workflow}")

        # Leave the Rich display on permanently
        while display == Display.RICH:
            ...

from textual.app import App, ComposeResult
from textual import work, events
from textual.widgets import Header, Footer, Placeholder, Label, Static, RichLog, Tree
from textual.containers import VerticalScroll, HorizontalScroll
from textual.reactive import reactive
from time import monotonic

class TaskTree(Tree):
    DEFAULT_CSS = """
    TaskTree {
        column-span: 2;
        height: 100%;
        border: solid yellow;
    }
    """
    pass

class Progress(Static):
    DEFAULT_CSS = """
    Progress {
        column-span: 2;
        height: 100%;
        border: solid green;
    }
    """

class Resources(Static):
    DEFAULT_CSS = """
    Resources {
        column-span: 1;
        height: 100%;
        border: solid blue;
    }
    """

class Log(RichLog):
    DEFAULT_CSS = """
    Log {
        column-span: 5;
        height: 100%;
        border: solid red;
    }
    """

class WorkflowApp(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 5;
        grid-rows: 60% 40%;
    }

    .resources {
        column-span: 1;
        height: 100%;
        border: solid yellow;
    }

    .log {
        column-span: 5;
        height: 100%;
        border: solid yellow;
    }
    """

    messages = []

    def __init__(self, fps:int=60, workflow:dict={}):
        self.fps = fps
        self.workflow = workflow
        super().__init__()

    def compose(self) -> ComposeResult:
        self.header = Header()
        yield self.header
        self.footer = Footer()
        yield self.footer

        self.task_tree = TaskTree("Tree")
        yield self.task_tree
    
        self.progress = Progress("Progress")
        yield self.progress
    
        self.resources = Resources("Resources")
        yield self.resources

        self.run_log = Log(highlight=True, markup=True)
        yield self.run_log

    def on_mount(self) -> None:
        self.title = "Title"
        self.sub_title = "Subtitle"

        self.gui = self.set_interval(1 / self.fps, self.update_gui)
        self.gui.resume()
        self.messages.append("GUI Loaded")
        self.run_workflow()

    @work
    async def update_gui(self) -> None:
        self.update_log()

    def update_log(self) -> None:
        messages, self.messages = self.messages, []
        for message in messages:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.run_log.write(f"{now} [INFO] {message}")

    @work(thread=True)
    async def run_workflow(self) -> None:
        self.messages.append("Doing slow work!")
        time.sleep(3)
        self.messages.append("Finished slow work.")

    def on_key(self, event: events.Key) -> None:
        self.messages.append(event)
    


if __name__ == "__main__":

    options = get_cli_options()
    kwargs = vars(options)
    #asyncio.run(main(**kwargs))

    app = WorkflowApp()
    app.run()

