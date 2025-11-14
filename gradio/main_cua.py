import gradio as gr
import json
from PIL import Image
import os
import requests
import glob
from data_loader import (
    _load_crmbench_cua
)


# DEFAULT_EXP_DIR = '../examples/sample_outputs'
DEFAULT_EXP_DIR = '../outputs'

ALL_CATEGORIES = ['admin', 'sales', 'service']
INSTANCE_TO_CATEGORY = {}
with open("../data/test_zero_shot.json", "r") as f:
    DATA = json.load(f)
for sample in DATA:
    sample_category = sample['task_id'].split('_')[0]
    INSTANCE_TO_CATEGORY[str(sample['task_id'])] = sample_category


INSTANCE_TO_INSTRUCTION = {}
for sample in DATA:
    INSTANCE_TO_INSTRUCTION[str(sample['task_id'])] = sample['query']

def get_dirs(log_dir):
    """Returns a list of directories inside the given log_dir."""
    if os.path.isdir(log_dir):
        # return [d for d in os.listdir(log_dir) if os.path.isdir(os.path.join(log_dir, d)) and 'debug' not in d]
        return [d for d in os.listdir(log_dir) if os.path.isdir(os.path.join(log_dir, d))]
    return []


with gr.Blocks() as demo:
    with gr.Tab(label="SCUBA Computer-use Agents Trajectory Visualizer"):
        gr.Markdown("""
            ## Load Data
            """)
        
        with gr.Row():
            outputs_dir_ui = gr.Textbox(value=DEFAULT_EXP_DIR, label="Outputs Directory", interactive=True)
            
            select_runname_ui = gr.Dropdown(choices=['--select--'] + sorted(get_dirs(DEFAULT_EXP_DIR), reverse=True), label="Run Name", interactive=True)
            def update_runname(log_dir):
                all_runnames = get_dirs(log_dir)
                sorted_runnames = sorted(all_runnames, reverse=True)
                return gr.Dropdown(choices=['--select--'] + sorted_runnames, label="Run Name", interactive=True)
            outputs_dir_ui.change(update_runname, inputs=[outputs_dir_ui], outputs=[select_runname_ui])
            
            number_of_tasks_found_ui = gr.Textbox(value='---', label="Number of Tasks Found", interactive=False)
            def update_number_of_tasks_found(outputs_dir, runname):
                total_instance_found = len(get_dirs(os.path.join(outputs_dir, runname, 'trajectory')))
                return gr.Textbox(value=f"{total_instance_found}", label="Number of Tasks Found", interactive=False)
            select_runname_ui.change(update_number_of_tasks_found, inputs=[outputs_dir_ui, select_runname_ui], outputs=[number_of_tasks_found_ui])
        
        with gr.Row():
            with gr.Column():
                select_category_ui = gr.Dropdown(choices=['--select--'] + sorted(ALL_CATEGORIES), label="Select Task Category", interactive=True)
                
                select_task_instance_ui = gr.Dropdown(choices=['--select--'], label="Select Task Instance", interactive=True)
                def update_task_instance(outputs_dir, runname, category):
                    all_task_instances_folders = get_dirs(os.path.join(outputs_dir, runname, 'trajectory'))
                    task_instances_in_this_category = [instance for instance in all_task_instances_folders if INSTANCE_TO_CATEGORY[instance] == category]
                    task_instances_in_this_category_sorted = sorted(task_instances_in_this_category)
                    if len(task_instances_in_this_category_sorted) == 0:
                        task_instances_in_this_category_sorted = sorted(
                            task_instances_in_this_category,
                            key=lambda x: tuple(int(part) if part.isdigit() else part for part in x.split('_'))
                        )
                    return gr.Dropdown(choices=['--select--'] + task_instances_in_this_category_sorted, label="Select Task Instance", interactive=True)
                    task_instances_in_this_category_sorted = sorted(task_instances_in_this_category)
                    if len(task_instances_in_this_category_sorted) == 0:
                        task_instances_in_this_category_sorted = sorted(
                            task_instances_in_this_category,
                            key=lambda x: tuple(int(part) if part.isdigit() else part for part in x.split('_'))
                        )
                    return gr.Dropdown(choices=['--select--'] + task_instances_in_this_category_sorted, label="Select Task Instance", interactive=True)
                select_category_ui.change(update_task_instance, inputs=[outputs_dir_ui, select_runname_ui, select_category_ui], outputs=[select_task_instance_ui])
                
                select_task_run_ui = gr.Dropdown(choices=['--select--'], label="Select Task Run", interactive=True)
                def update_task_run(outputs_dir, runname, category, task_instance):
                    all_task_runs_folders = get_dirs(os.path.join(outputs_dir, runname, 'trajectory', task_instance))
                    return gr.Dropdown(choices=['--select--'] + all_task_runs_folders, label="Select Task Run", interactive=True)
                select_task_instance_ui.change(update_task_run, inputs=[outputs_dir_ui, select_runname_ui, select_category_ui, select_task_instance_ui], outputs=[select_task_run_ui])
            with gr.Column():
                eval_results_ui = gr.JSON(label="Evaluation Result")
            
        with gr.Row():
            show_instruction_ui = gr.Textbox(value='---', label="Task Instruction", interactive=False)
            def update_instruction(outputs_dir, runname, category, task_instance, task_run):
                instruction = INSTANCE_TO_INSTRUCTION[str(task_instance)]
                return gr.Textbox(value=instruction, label="Task Instruction", interactive=False)
            select_task_run_ui.change(update_instruction, inputs=[outputs_dir_ui, select_runname_ui, select_category_ui, select_task_instance_ui, select_task_run_ui], outputs=[show_instruction_ui])

            
        with gr.Row():            
            def load_trajectory(outputs_dir, runname, category, task_instance, task_run):
                target_dir = os.path.join(outputs_dir, runname, 'trajectory', task_instance, task_run)
                print("loading trajectory from", target_dir)
                results, evaluation_result = _load_crmbench_cua(target_dir)
                total_steps = len(results)
                first_step = results[0]
                image = first_step.get("screenshot", None)
                step_text = f"Step: 1 / {total_steps}"
                
                
                first_step_data = {k: v for k, v in first_step.items() if k != "screenshot"}
                
                runtime_log_file = os.path.join(target_dir, "runtime.log")
                with open(runtime_log_file, "r") as f:
                    runtime_log = f.read()
                
                return results, 0, first_step_data, image, step_text, evaluation_result, runtime_log
            
            
            def update_step(results, step):
                total_steps = len(results)
                if not results or step < 0 or step >= total_steps:
                    return step, {}, None, f"Step: {step+1} / {total_steps}"

                current_step = results[step]
                image = current_step.get("screenshot", None)
                step_text = f"Step: {step+1} / {total_steps}"
                
                # Add task ID and category to step data
                step_data = {k: v for k, v in current_step.items() if k != "screenshot"}
                
                return step, step_data, image, step_text
            
            # Move to next step
            def next_step(results, step):
                """Handles next step logic."""
                new_step = min(step + 1, len(results) - 1)
                return update_step(results, new_step)

            # Move to previous step
            def prev_step(results, step):
                """Handles previous step logic."""
                new_step = max(step - 1, 0)
                return update_step(results, new_step) 
            
            with gr.Column():
                image_output_ui = gr.Image(label="Step Screenshot (before the action)")
            
            with gr.Column():
                step_ui = gr.Textbox(value="Step: 0 / 0", label="Step Counter (if total #steps > max steps, then it means there are steps with more then 1 action.)", interactive=False)   
                with gr.Row():
                    prev_button = gr.Button("Prev")
                    next_button = gr.Button("Next")
                json_output_ui = gr.JSON(label="Step Data")
                


        with gr.Row():
            show_runtime_log_ui = gr.Textbox(value='---', label="Runtime Log", interactive=False)
        results_state = gr.State([])  # Stores loaded steps
        step_state = gr.State(0)
        select_task_run_ui.change(
            load_trajectory, 
            inputs=[outputs_dir_ui, select_runname_ui, select_category_ui, select_task_instance_ui, select_task_run_ui], 
            outputs=[results_state, step_state, json_output_ui, image_output_ui, step_ui, eval_results_ui, show_runtime_log_ui]
        )
            

        
        next_button.click(
                next_step, 
                inputs=[results_state, step_state], 
                outputs=[step_state, json_output_ui, image_output_ui, step_ui]
            )
            
        prev_button.click(
            prev_step, 
            inputs=[results_state, step_state], 
            outputs=[step_state, json_output_ui, image_output_ui, step_ui]
        )
    
            
if __name__ == '__main__':
    demo.launch(
        server_name="0.0.0.0",
        server_port=2020,
        share=True,
        debug=True
    )                            