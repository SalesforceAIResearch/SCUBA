import gradio as gr
import json
from PIL import Image
import os
import requests
from data_loader import (
    _load_browser_use
)

DEFAULT_EXP_DIR = '../examples/sample_outputs'
with open("../data/test_zero_shot.json", "r") as f:
    DATA = json.load(f)
    TASK_ID_TO_CONFIG = {sample['task_id']: sample for sample in DATA}


def get_dirs(log_dir):
    """Returns a list of directories inside the given log_dir."""
    if os.path.isdir(log_dir):
        # return [d for d in os.listdir(log_dir) if os.path.isdir(os.path.join(log_dir, d)) and 'debug' not in d]
        res = [d for d in os.listdir(log_dir) if os.path.isdir(os.path.join(log_dir, d))]
        res.sort()
        print(res)
        return res
    return []

ALL_DIRS = get_dirs(DEFAULT_EXP_DIR) 
with gr.Blocks() as demo:
    with gr.Tab(label="SCUBA Browser-use Agents Trajectory Visualizer"):
        gr.Markdown("""
            ## Load Data
            """)
        
        with gr.Row():
            trajectory_dir_ui = gr.Dropdown(choices=['--select--'] + ALL_DIRS,
                                        label="Trajectory Directory",
                                        interactive=True
                                    )


            performance_stats_ui = gr.Textbox(label="Performance Statistics", interactive=False)
            def compute_performance_stats(log_dir):
                """Computes and returns total JSONs, successful JSONs, and failed JSONs from 'performance' folder."""
                performance_path = os.path.join(DEFAULT_EXP_DIR, log_dir, "performance")
                print(performance_path)
                if not os.path.isdir(performance_path):
                    return "No performance directory found."

                total = 0
                success = 0
                fail = 0

                for file in os.listdir(performance_path):
                    if file.endswith(".json"):
                        total += 1
                        with open(os.path.join(performance_path, file), "r") as f:
                            data = json.load(f)
                            evaluation_result = data.get("evaluation_result", {})
                            if evaluation_result.get("Score") == 1:
                                success += 1
                            else:
                                fail += 1
                
                return f"Total {total} | Success: {success} | Fail: {fail}"
            trajectory_dir_ui.change(compute_performance_stats, inputs=[trajectory_dir_ui], outputs=[performance_stats_ui])
        with gr.Row():
            with gr.Column(scale=1):
                filter_ui = gr.Dropdown(choices=["Show All", "Success Only", "Failed Only"],
                                    value="Show All", label="Filter", interactive=True)
                choose_traj_ui = gr.Dropdown(choices=[], label="List of Trajectories", interactive=True)
            with gr.Column(scale=2):
                performance_json_ui = gr.JSON(label="Performance JSON Data")
            def update_all_trajectories(log_dir, filter_option):
                """Lists trajectories based on filter selection."""
                search_path = os.path.join(DEFAULT_EXP_DIR, log_dir, "trajectory")
                performance_path = os.path.join(DEFAULT_EXP_DIR, log_dir, "performance")
                
                if not os.path.isdir(search_path):
                    return gr.Dropdown(choices=[], label="List of Trajectories", interactive=True)

                choices = []
                filter_map = {"Show All": None, "Success Only": 1, "Failed Only": 0}

                for file in os.listdir(search_path):
                    if file.endswith(".json"):
                        if filter_option in filter_map:
                            perf_file = os.path.join(performance_path, file)
                            if os.path.exists(perf_file):
                                try:
                                    with open(perf_file, "r") as f:
                                        data = json.load(f)
                                        evaluation_result = data.get("evaluation_result", {})
                                        # breakpoint()
                                        if filter_map[filter_option] is None or evaluation_result.get("Score") < 1:
                                            choices.append(file)
                                except Exception as e:
                                    pass  # Ignore corrupted performance files
                            else:
                                if filter_option == "Show All":  # Include unmatched if showing all
                                    choices.append(file)
                        else:
                            choices.append(file)

                # Sort numerically by filename (assuming format "{id}.json")
                try:
                    choices.sort(key=lambda x: int(x.split(".")[0]))
                except Exception as e:
                    choices.sort()

                # Prepend the number of samples in this filter
                choices.insert(0, f"{len(choices)} samples found")

                return gr.Dropdown(choices=choices, label="List of Trajectories", interactive=True)
            def load_performance_json(log_dir, selected_json):
                
                if not selected_json or "samples found" in selected_json:
                    return {}  # Ignore if selection is empty or placeholder text
                
                
                performance_json_path = os.path.join(DEFAULT_EXP_DIR, log_dir, "performance", selected_json)
                if not os.path.exists(performance_json_path):
                    return {"error": "File not found"}
                
                try:
                    with open(performance_json_path, "r") as f:
                        data = json.load(f)
                        return {
                            "evaluation_result": data.get("evaluation_result", "N/A"),
                            "time (min)": round(data.get("time (min)", "-1"), 2),
                        }
                except Exception:
                    return {"error": "Failed to load or parse JSON"}
            

            filter_ui.change(update_all_trajectories, inputs=[trajectory_dir_ui, filter_ui], outputs=[choose_traj_ui])
            

            
            trajectory_dir_ui.change(update_all_trajectories, 
                            inputs=[trajectory_dir_ui, filter_ui], outputs=[choose_traj_ui])
            choose_traj_ui.change(load_performance_json, 
                                  inputs=[trajectory_dir_ui, choose_traj_ui], 
                                  outputs=[performance_json_ui])
        with gr.Row():
            json_output_ui = gr.JSON(label="Config JSON Data", show_indices=True, max_height=400)
            def load_config_json(log_dir, selected_json):
                if not selected_json or "samples found" in selected_json:
                    return {}
                try:
                    task_id = selected_json.split(".json")[0]
                    task_instance_dict = TASK_ID_TO_CONFIG[task_id]
                    category = task_instance_dict.get("category", "N/A")
                    subcategory = task_instance_dict.get("subcategory", "N/A")
                    query = task_instance_dict.get("query", "N/A")
                    ground_truth_dict = task_instance_dict.get("ground_truth_dict", "N/A")
                    difficulty = task_instance_dict.get("difficulty", "N/A")
                    return {
                        "category": category,
                        "subcategory": subcategory,
                        "query": query,
                        "ground_truth_dict": ground_truth_dict,
                        "difficulty": difficulty,
                    }
                except Exception as e:
                    print(str(e))
                    return {"error": "Failed to load or parse JSON"}
            
            choose_traj_ui.change(load_config_json, inputs=[trajectory_dir_ui, choose_traj_ui], outputs=[json_output_ui])

            
        with gr.Row():
            # Load trajectory JSON and reset step
            def load_trajectory_json(log_dir, selected_json):
                if not selected_json or "samples found" in selected_json:
                    return [], 0, {"error": "File not found"}, None, "Step: 0 / 0"
                
                json_path = os.path.join(DEFAULT_EXP_DIR, log_dir, "trajectory", selected_json)
                if not os.path.exists(json_path):
                    return [], 0, {"error": "File not found"}, None, "Step: 0 / 0"
                
                results = _load_browser_use(json_path)
                total_steps = len(results)
                if total_steps == 0:
                    return [], 0, {"error": "No steps found"}, None, "Step: 0 / 0"
                
                first_step = results[0]
                image = first_step.get("screenshot", None)
                step_text = f"Step: 1 / {total_steps}"
                json_details = {k: v for k, v in first_step.items() if k != "screenshot"}
                return results, 0, json_details, image, step_text

            # Update step and outputs
            def update_step(results, step):
                total_steps = len(results)
                if not results or step < 0 or step >= total_steps:
                    return step, {}, None, f"Step: {step+1} / {total_steps}"

                current_step = results[step]
                image = current_step.get("screenshot", None)
                step_text = f"Step: {step+1} / {total_steps}"
                return step, {k: v for k, v in current_step.items() if k != "screenshot"}, image, step_text


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
                image_output_ui = gr.Image(label="Step Screenshot")
            
            with gr.Column():
                step_ui = gr.Textbox(value="Step: 0 / 0", label="Step Counter", interactive=False)   
                with gr.Row():
                    prev_button = gr.Button("Prev")
                    next_button = gr.Button("Next")
                json_output_ui = gr.JSON(label="Step Data", show_indices=True, max_height=400)
            
            results_state = gr.State([])  # Stores loaded steps
            step_state = gr.State(0) 
            choose_traj_ui.change(load_trajectory_json,
                                  inputs=[trajectory_dir_ui, choose_traj_ui],
                                  outputs=[results_state, step_state, json_output_ui, image_output_ui, step_ui])

            next_button.click(next_step, inputs=[results_state, step_state], outputs=[step_state, json_output_ui, image_output_ui, step_ui])
            prev_button.click(prev_step, inputs=[results_state, step_state], outputs=[step_state, json_output_ui, image_output_ui, step_ui])

                
if __name__ == '__main__':
    demo.launch(
        server_name="localhost",
        server_port=11451,
        share=True,
        debug=True
    )                