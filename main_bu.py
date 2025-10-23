import argparse
import json
import logging
import asyncio
import time
import os
os.environ["TOKENIZERS_PARALLELISM"] = "false"
from pathlib import Path
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI


from typing import Union, Dict, List
import traceback
import glob
from playwright.async_api import async_playwright

from utils import run_evaluate, run_reset, LogFormatter, split_task_config_pool_into_batches
from args import get_args

from scuba.phases.evaluation.master_evaluator import MilestoneEvaluator
from scuba.phases.resetter import Resetter
from scuba.helpers.salesforce_commands import authorize_using_access_token, install_initial_data, retrieve_initial_state_metadata, create_project_if_not_exists
# build env and agent
from browser_use import Controller
from browser_use.controller.views import NoParamsAction
from browser_use.agent.views import ActionResult

from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContextConfig
from browser_use.custom.browser_zoo import BrowserBugFix
from browser_use.custom.browser_context_zoo import BrowserContextBugFix

from browser_use.custom.agent_zoo import AgentWithCustomPlanner
from browser_use.custom.trajectory_parser import agent_trajectory_parser
from browser_use.custom.utils import create_llm, summarize_usage_info_from_jsonfied_trajectory, LoginInCredentials



logger = logging.getLogger(__name__)
load_dotenv(override=True)
PAUSE_AFTER_LOGIN = 10
class BrowserUseFormatter(logging.Formatter):
    def format(self, record):
        if type(record.name) == str and record.name.startswith('browser_use.'):
            record.name = record.name.split('.')[-2]
        return super().format(record)
    
def add_task_log_handler(task_id, args):
    """Dynamically add a file handler for a specific task."""
    LOG_FOLDER = os.path.join(args.result_dir, "logs")
    Path(LOG_FOLDER).mkdir(parents=True, exist_ok=True)
    log_file = os.path.join(LOG_FOLDER, f"{task_id}.log")
    task_logger = logging.getLogger(f"task_{task_id}")
    task_logger.setLevel(logging.INFO)
    for handler in task_logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath(log_file):
            return task_logger, handler  # Return existing logger and handler

    # Create and add a new file handler
    file_handler = logging.FileHandler(log_file, mode="w")
    file_handler.setLevel(logging.INFO)
    # Define log format
    file_handler.setFormatter(BrowserUseFormatter('%(levelname)-8s [%(name)s] %(message)s'))
    # Attach the handler to the existing logger
    task_logger.addHandler(file_handler)
    return task_logger, file_handler  # Return logger and handler to remove later

def remove_task_log_handler(task_logger, file_handler):
    """Remove a specific file handler after task completion."""
    if file_handler in task_logger.handlers:
        task_logger.removeHandler(file_handler)
        file_handler.close()  # Close the file properly          


async def aevaluate_single_task_bu(    
    args: argparse.Namespace,
    task_instance_dict: dict,
    browser_agent_llm: Union[ChatOpenAI, ChatGoogleGenerativeAI, None],
    planner_llm_wo_vision: Union[ChatOpenAI, ChatGoogleGenerativeAI, None],
    planner_llm_with_vision: Union[ChatOpenAI, ChatGoogleGenerativeAI, None],
    retriever: Union[None],
    narrative_memory_summarizer_llm: Union[ChatOpenAI, ChatGoogleGenerativeAI, None],
    task_logger = None,
    ):  
    jsonfied_trajectory = []  
    score = 0
    token_usage_data = {}
    browser = None
    context = None
    images = []
    try:
        if task_logger is None:
            this_task_logger = logger
        else:
            this_task_logger = task_logger
            
       
        if len(images) > 0:
            planner_llm = planner_llm_with_vision
        else:
            planner_llm = planner_llm_wo_vision
        if len(images) > 0:
            use_vision_for_planner = True
        else:
            use_vision_for_planner = False
        query = task_instance_dict['query']
        task_id = task_instance_dict['task_id']
        this_task_logger.info(f"[Query]: {query}")
        this_task_logger.info(f"[Use vision for planner]: {use_vision_for_planner} because there are {len(images)} images")
        if args.headless:
            is_headless = True
        else:
            is_headless = False
        browser_config = BrowserConfig(headless=is_headless)
        browser = BrowserBugFix(browser_config)

            
        context_config = BrowserContextConfig(
            minimum_wait_page_load_time = 0.5,
            browser_window_size={'width': args.viewport_width, 'height': args.viewport_height},
        )
        context = BrowserContextBugFix(browser=browser, 
                                       config=context_config,
                                       storage_state_file_path=args.storage_state_file_path
                                       )
        retrieved_narrative_memory = []
        # add custom actions
        credentials = LoginInCredentials(username=os.environ.get("SALESFORCE_USERNAME",""), 
                                    password=os.environ.get("SALESFORCE_PASSWORD", ""))
        assert credentials.username != "", "Please set the environment variable SALESFORCE_USERNAME"
        assert credentials.password != "", "Please set the environment variable SALESFORCE_PASSWORD"
        
        controller = Controller(exclude_actions=['search_google'])
        @controller.action('Login to Salesforce website', param_model=LoginInCredentials)
        async def login_salesforce(params: LoginInCredentials, browser: BrowserContextBugFix) -> ActionResult:
            page = await browser.get_current_page()
            await page.goto("https://login.salesforce.com")
            await page.get_by_label("Username").click()
            await page.get_by_label("Username").fill(params.username)
            await page.get_by_label("Password").click()
            await page.get_by_label("Password").fill(params.password)
            await page.get_by_role("button", name="Log In").click()
            # logger.info(f"Waiting for {PAUSE_AFTER_LOGIN} seconds after clicking login button since salesforce can be slow to load...")
            await asyncio.sleep(PAUSE_AFTER_LOGIN)
            action_result = ActionResult(extracted_content="Salesfoce Login successful.")
            # await asyncio.sleep(60)

            # if we are in the lightning UI (since the agent might swicth to the classic UI in some runs)
            url = page.url
            if "lightning" not in url:
                new_url = url.split('.')[:2]
                new_url = '.'.join(new_url)
                new_url = f"{new_url}.lightning.force.com/lightning/page/home"
                await page.goto(new_url)
                await asyncio.sleep(PAUSE_AFTER_LOGIN)

            # navigate to sales app
            await page.get_by_role("button", name="App Launcher").click()
            try:
                await page.get_by_placeholder("Search apps and items...").fill("sales")
                await page.get_by_role("option", name="Sales", exact=True).click()
                action_result = ActionResult(extracted_content="Salesfoce Login successful")
            except TimeoutError as e:
                action_result = ActionResult(extracted_content="Salesfoce Login; failed to navigate to sales app")
                # for orgs does not have sales app, we use digital experiences as a fallback
                try:
                    await page.get_by_placeholder("Search apps and items...").fill("Salesforce Chatter")
                    await page.get_by_role("option", name="Salesforce Chatter", exact=True).click()
                except TimeoutError as e:
                    # we just do nothing here
                    logger.warning(f"{str(e)}.\n Skip the initialization.")
                    pass
            return action_result

        initial_actions = [{'login_salesforce': {"username": credentials.username, "password": credentials.password}}]
        
        
        @controller.action("Call external planner agent to revise the current plan. This action should be called when the browser agent feels getting stuck in a loop, cannot recover from the error, or is unable to make progress.", param_model=NoParamsAction)
        async def replan(param_model:NoParamsAction, browser: BrowserContextBugFix) -> ActionResult:
            return ActionResult(extracted_content="Re-plan signal received", include_in_memory=True)
            
        agent = AgentWithCustomPlanner(task=query,
                        llm=browser_agent_llm,
                        browser_context=context,
                        controller=controller,
                        initial_actions=initial_actions,
                        generate_gif=False,
                        planner_llm=planner_llm,
                        planner_interval=args.planner_interval, # large number to encourage auto-replan
                        use_vision_for_planner=use_vision_for_planner,
                        planner_inputs = {'retrived_narrative_memory': retrieved_narrative_memory},
                        max_actions_per_step = args.max_actions_per_step,
                        use_budget = args.use_budget,
                        budget = args.budget,
                        input_token_price_per_million = args.input_token_price_per_million,
                        output_token_price_per_million = args.output_token_price_per_million
                        )
        history, current_page = await agent.run(max_steps=args.max_steps)
        agent_answer = history.final_result()
        
        async with asyncio.Lock():
            try:
                evaluator = MilestoneEvaluator(args.org_alias)
                # breakpoint()
                score_card = evaluator.evaluate_instance(task_instance_dict, agent_answer)
                evaluation_result = score_card.__dict__()
            except Exception as e:
                evaluation_result = {
                    'System Failiures': {'error': str(e), 'traceback': traceback.format_exc()},
                    'Score': -1,
                    'Task Complete': "N/A; since the evaluation failed",
                    'Failure Reasons': "see system failures",
                    'Rubric': "N/A; since the evaluation failed"
                }
        is_task_complete = score_card.task_complete
        if is_task_complete:
            this_task_logger.info(f"[Result] (PASS) {task_id}")
        else:
            this_task_logger.info(f"[Result] (FAIL) {task_id} - final score: {score}")
        

       
        jsonfied_trajectory = agent.get_jsonfied_trajectory()
        trajectory_path = os.path.join(args.result_dir, "trajectory")
        if not os.path.exists(trajectory_path):
            os.makedirs(trajectory_path, exist_ok=True)
            
        agent_generated_trajectory_path = os.path.join(trajectory_path, f"{task_id}.json")
        with open(agent_generated_trajectory_path, 'w') as f:
            traj_data = {
                'task_prompt': query,
                'is_successful': int(score) == 1,
                'steps': jsonfied_trajectory
            }
            json.dump(traj_data, f, indent=4) 

        

        narrative_memory_summary_usage = {}
        
        browser_agent_usage = summarize_usage_info_from_jsonfied_trajectory(jsonfied_trajectory)
        
        token_usage_data = {
            'browser_agent_usage': browser_agent_usage,
            'narrative_memory_summary_usage': narrative_memory_summary_usage
        }
            
    except Exception as e:
        this_task_logger.info(f"[Unhandled Error] {repr(e)}]")
        # write to error file
        error_dir = os.path.join(args.result_dir, "error")
        if not os.path.exists(error_dir):
            os.makedirs(error_dir, exist_ok=True)
        error_file = os.path.join(error_dir, f"{task_id}.txt")
        with open(error_file, "w") as f:
            f.write(f"[Task ID]: {task_id}\n")
            f.write(f"[Query]: {query}\n")
            f.write(f"[Unhandled Error] {repr(e)}\n")
            f.write(traceback.format_exc())  # write stack trace to file
    finally:
        if browser is not None:
            await browser.close()
        if context is not None:
            await context.close()
    return evaluation_result, token_usage_data


async def evaluate_single_task_wrapper(
        semaphore: asyncio.Semaphore,
        task_instance_dict: dict,
        args: argparse.Namespace,
        additional_kwargs: dict
    ) -> None:
    """Wrapper function to evaluate a single task and dynamically log to a separate file."""
    async with semaphore:
        task_id = task_instance_dict['task_id']
        logger.info(f"Starting evaluation for {task_id}")
        task_logger, file_handler = add_task_log_handler(task_id, args)
        try:
            start_time = time.time()
            task_logger.info(f"Starting evaluation for {task_id}")
            if args.solutions == 'bu':

                # breakpoint()
                evaluation_result, token_usage_data  = await aevaluate_single_task_bu(args, 
                                                    task_instance_dict, 
                                                    additional_kwargs['browser_agent_llm'],
                                                    additional_kwargs['planner_llm_wo_vision'],
                                                    additional_kwargs['planner_llm_with_vision'],
                                                    additional_kwargs['retriever'],
                                                    additional_kwargs['narrative_memory_summarizer_llm'],
                                                    task_logger)
            else:
                raise ValueError(f"Solutions: {args.solutions} is not supported.")

            time_spent = time.time() - start_time
            task_logger.info(f"Task {task_id} took {time_spent} seconds")
            
            task_logger.info(f"usage: {token_usage_data}")
            performance = {
                'task_id': task_id,
                'usage': token_usage_data,
                'evaluation_result': evaluation_result,
                'time (min)': time_spent / 60
            }
            performance_path = os.path.join(args.result_dir, "performance")
            if not os.path.exists(performance_path):
                os.makedirs(performance_path, exist_ok=True)
            with open(os.path.join(performance_path, f"{task_id}.json"), 'w') as f:
                json.dump(performance, f, indent=4)
            return
        except Exception as e:
            task_logger.error(f"Error in task {task_id}: {repr(e)}")
            error_dir = os.path.join(args.result_dir, "error")
            error_file = os.path.join(error_dir, f"{task_id}.txt")
            with open(error_file, "w") as f:
                f.write(f"[Task ID]: {task_id}\n")
                f.write(f"[Unhandled Error] {repr(e)}\n")
                f.write(traceback.format_exc())  # write stack trace to file
            return
        finally:
            remove_task_log_handler(task_logger, file_handler)


async def test(args: argparse.Namespace, task_config_pool: List[Dict]) -> None:
    if len(task_config_pool) == 0:
        logger.info("No tasks to evaluate.")
        return
    try:
        authorize_using_access_token(args.org_alias)
        retrieve_initial_state_metadata(args.org_alias)
        install_initial_data(args.org_alias, task_config_pool)
        create_project_if_not_exists(os.path.join('orgs', 'modified_state', args.org_alias), args.org_alias)
        
        task_config_pool_batches = split_task_config_pool_into_batches(task_config_pool, args)
        total_batches = len(task_config_pool_batches)
        logger.info(f"Split the task_config_pool into {total_batches} batches due to constraints and dependencies of different tasks")
        
        if args.reset_orgs_before_eval:
            # Since the reset and evaluation are based on local files; we need to reset the salesforce orgs first
            logger.info(f"Bulk resetting the salesforce orgs...")
            time_start = time.perf_counter()
            run_reset(task_config_pool, args.org_alias)
            time_end = time.perf_counter()
            logger.info(f"Done bulk resetting the salesforce orgs in {time_end - time_start:.2f} seconds")
        if args.solutions == 'bu':
            # build auxilary components
            retriever = None
            narrative_memory_summarizer_llm = None
            if args.use_planner:
                planner_llm_wo_vision = create_llm(args.provider, args.planner_model_wo_vision, args.planner_temperature)
                planner_llm_with_vision = create_llm(args.provider, args.planner_model_with_vision, args.planner_temperature)
                logger.info(f"\033[32m{args.planner_model_wo_vision} is used for planner.\033[0m")  
                logger.info(f"\033[32m{args.planner_model_with_vision} is used for planner with vision.\033[0m")  
            else:
                raise ValueError("The current implementation only supports the use of a planner.")
                
            browser_agent_llm = create_llm(args.provider, args.browser_agent_model)
            
            additional_kwargs = {
                'browser_agent_llm': browser_agent_llm,
                'planner_llm_wo_vision': planner_llm_wo_vision,
                'planner_llm_with_vision': planner_llm_with_vision,
                'retriever': retriever,
                'narrative_memory_summarizer_llm': narrative_memory_summarizer_llm
            } 
        else:
            raise ValueError(f"Solutions: {args.solutions} is not supported.")
        
        # tasks are evaluated in batches
        for batch_idx, task_config_pool in enumerate(task_config_pool_batches):
            num_tasks = len(task_config_pool)
            logger.info(f"Starting batch {batch_idx} with {num_tasks} tasks")
            semaphore = asyncio.Semaphore(args.max_concurrent_tasks)
            job_queue = []
            for task_instance_dict in task_config_pool:
                job_queue.append(evaluate_single_task_wrapper(semaphore, 
                                                            task_instance_dict, 
                                                            args,                                                   additional_kwargs))
            try:
                await asyncio.gather(*job_queue)
            except Exception as e:
                logger.error(f"Error message: {str(e)}")
            finally:
                try:
                    async with async_playwright() as p:
                        await p.stop()
                except Exception as e:
                    logger.error(f"Error stopping Playwright: {e}")
    except Exception as e:
        logger.error(f"Error in evaluation: {e}")
        logger.error(traceback.format_exc())
        raise e                    


def get_unfinished_task_ids(task_instance_dicts: List[Dict], target_dir: str):
    all_task_ids = [task_instance["task_id"] for task_instance in task_instance_dicts]
    unfinished_task_ids = []
    for task_id in all_task_ids:
        if not os.path.exists(os.path.join(target_dir,  f'{task_id}.json')):
            unfinished_task_ids.append(task_id)
    return unfinished_task_ids




if __name__ == '__main__':
    args = get_args()
    assert args.org_alias == os.getenv("ORG_ALIAS"), f"org_alias: {args.org_alias} is not the same as the org_alias in the .env file: {os.getenv('ORG_ALIAS')}. The one in the .env file is used to login in the remote desktop environment."
    args.result_dir = os.path.join(args.result_dir, args.run_name)
    
    assert args.total_desired_envs == args.max_concurrent_tasks, f"total_desired_envs: {args.total_desired_envs} is not the same as max_concurrent_tasks: {args.max_concurrent_tasks}"

    if not os.path.exists(args.result_dir):
        os.makedirs(args.result_dir, exist_ok=True)
        logger.info(f"Create result directory: {args.result_dir}")
    
    main_log_file = os.path.join(args.result_dir, "main.log")
    for handler in logger.handlers:
        if isinstance(handler, logging.FileHandler) and handler.baseFilename == os.path.abspath(main_log_file):
           pass
    # Create and add a new file handler
    file_handler = logging.FileHandler(main_log_file, mode="w")
    file_handler.setLevel(logging.DEBUG)
    # Define log format
    file_handler.setFormatter(BrowserUseFormatter('%(levelname)-8s [%(name)s] %(message)s'))
    # Attach the handler to the existing logger
    logger.addHandler(file_handler)
    # load all task instances
    with open(args.query_instance_file, "r") as f:
        task_instance_dicts = json.load(f)
        
    # set up task config pool
    if not args.rerun_failed_tasks:
        if args.run_as_debug_mode:
            target_task_ids = args.debug_task_id_list
            # target_task_ids = []
            # for task_instance in task_instance_dicts:
            #     if task_instance["task_id"].startswith("admin"):
            #         target_task_ids.append(task_instance["task_id"])
            # print('admin tasks: ', len(target_task_ids))
            tasks_to_eval = [task_instance for task_instance in task_instance_dicts if str(task_instance["task_id"]) in target_task_ids]
            logger.info(f"Debug mode: only evaluate {len(tasks_to_eval)} tasks")
        else:
            target_dir = os.path.join(args.result_dir, "performance")
            unfinished_task_ids = get_unfinished_task_ids(task_instance_dicts, target_dir)
            tasks_to_eval = [task_instance for task_instance in task_instance_dicts if task_instance["task_id"] in unfinished_task_ids]
            logger.info(f"[{len(tasks_to_eval)}] tasks remaining to evaluate out of [{len(task_instance_dicts)}] total tasks")
        
        task_config_pool = [task for task in tasks_to_eval for _ in range(args.n_eval)]
    else:
        logger.info(f"Entering the Rerunning failed tasks mode...")
        logger.info("not implemented yet")
        exit(1)
    if args.skip_template_without_memory:
        task_template_to_skip = ['admin_006', 'admin_007', 'admin_039', 'sales_013', 'sales_014', 'sales_015', 'service_011']
        task_template_to_skip.append('admin_021')
        task_config_pool = [task for task in task_config_pool if task['query_template_metadata']['template_id'] not in task_template_to_skip]
        logger.info(f"Skipped tasks with template ids in {task_template_to_skip}")
    logger.info(f"Set n_eval to {args.n_eval} --> Final total [{len(task_config_pool)}] tasks to evaluate")
    # input("Press Enter to continue...")
    start_time = time.time()
    asyncio.run(test(args, task_config_pool))
    logger.removeHandler(file_handler)
    end_time = time.time()
    print(f"Total runtime: {end_time - start_time}")
    file_handler.close()
