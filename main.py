#!/usr/bin/env python3

import time
import re
import copy
import subprocess
import asyncio

import yaml
from rich.progress import Progress, TextColumn, MofNCompleteColumn, BarColumn, TimeRemainingColumn
from joblib import Parallel, delayed

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
    

def main():
    with open("jobs.yaml") as infile:
        workflow = yaml.safe_load(infile)
    del infile

    with Progress(
        TextColumn("{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        MofNCompleteColumn("/"),
        TextColumn("[yellow]{task.fields[current]}")
        ) as progress:

            for job,job_data in workflow["jobs"].items():
                steps = job_data["steps"] if job_data != None and "steps" in job_data and job_data["steps"] != None else {}
                num_steps = len(steps)
                job_progress = progress.add_task(f"[red]{job}", total=num_steps, current="")

                if num_steps == 0:
                    progress.update(job_progress, advance=1)
                    continue
                for step,step_data in steps.items():
                    processes = dynamic_step(step_data)
                    step_progress = progress.add_task(f"    [red]{step}", total=len(processes), current=f"")
                    for p in processes:
                        current = ""
                        # Option 1. Function
                        if "function" in p:
                            args = p["args"] if "args" in p else {}
                            fn_def = "async def fn({args}): {f}".format(
                                args=",".join([k for k in args]),
                                f = p['function']
                            )                          
                            if len(args) > 0:
                                current = " ".join([f"{k}={v}" for k,v in args.items()])
                            else:
                                current = p['function']
                            current = f"\[{current}]"
                        elif "command" in p:
                            command = [word for word in p["command"].split(" ") if word != ""]
                            fn_def = "async def fn(): {f}".format(
                                f=f"subprocess.run({command}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)"
                            )
                            args = {}
                            current = f"\[{p['command']}]"
                        exec(fn_def, globals())  
                        asyncio.run(fn(**args))
                        progress.update(step_progress, advance=1, current=current)


if __name__ == "__main__":
    main()
