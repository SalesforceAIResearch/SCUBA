"""
This file handles the execution of agent-based tasks for the CRM benchmark pipeline.
It contains functions to run a task using a given template and query string, and manages the agent's interaction with the Salesforce org.
"""

import os
import sys
os.environ["ANONYMIZED_TELEMETRY"] = "false"
import json
import logging
from datetime import datetime
import asyncio

from browser_use import Controller
from browser_use.controller.views import NoParamsAction
from browser_use.agent.views import ActionResult


from browser_use.custom.agent_zoo import AgentWithCustomPlanner
from browser_use.custom.knowledge import (QueryRephraser, NarrativeMemorySummarizer)

from browser_use.custom.retriever.SimpleRetriever import SimpleRetriever
from browser_use.custom.trajectory_parser import human_trajectory_parser, tutorial_like_text_parser, agent_trajectory_parser

from browser_use.browser.browser import BrowserConfig
from browser_use.browser.context import BrowserContextConfig

from browser_use.custom.browser_zoo import BrowserBugFix
from browser_use.custom.browser_context_zoo import BrowserContextBugFix


from browser_use.custom.get_args import get_args
from browser_use.custom.utils import create_llm, summarize_usage_info_from_jsonfied_trajectory, get_login_controller_and_action, LoginInCredentials

logger = logging.getLogger(__name__)


def build_auxilary_components(args):
    # build the query rephraser
    rephraser_llm = create_llm(args.provider, args.query_rephraser_model)
    query_rephraser = QueryRephraser(llm=rephraser_llm, platform=args.platform, local_kb_path=args.local_kb_path)
    logger.info(f"\033[32mQuery rephraser llm is {args.query_rephraser_model}.\033[0m")

    # build the retriever
    retriever = SimpleRetriever(model_name=args.retriever_model_name, cache_dir=args.retriever_cache_dir)
    logger.info(f"\033[32mRetriever model is {args.retriever_model_name}.\033[0m")

    # build the narrative memory summarizer
    narrative_memory_summarizer_llm = create_llm(args.provider, args.narrative_memory_summarizer_model)
    narrative_memory_summarizer = NarrativeMemorySummarizer(llm=narrative_memory_summarizer_llm,
                                                            platform=args.platform, local_kb_path=args.local_kb_path)
    logger.info(f"\033[32mNarrative memory summarizer llm is {args.narrative_memory_summarizer_model}.\033[0m")


    # load the narrative memory
    with open(os.path.join(args.local_kb_path, "narrative_memory.json"), "r") as f:
        narrative_memory = json.load(f)
    task_pools = [*narrative_memory.keys()]
    retriever.add_documents(task_pools)
    logger.info(f"Retriever initialized with {len(task_pools)} documents.")

    return query_rephraser, retriever, narrative_memory, narrative_memory_summarizer

async def run_task(task_id, task_query):
    args = get_args()
    # add current date-time to task-id
    args.task_id = f'{task_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
    # build the auxilary components
    query_rephraser, retriever, narrative_memory, narrative_memory_summarizer = build_auxilary_components(args)

    # pipeline starts here
    # disable the query rephraser for sf tasks
    # rephrased_query, rephraser_usage = query_rephraser.formulate_query(task_query)
    # query_rephraser.save_rephrased_query(rephrased_query)
    # logger.info(f"\033[32mRe-phrased query: {rephrased_query}\033[0m")
    rephrased_query = task_query
    result = retriever.get_retrieved_docs(rephrased_query, top_k=args.retriever_top_k,
                                          threshold=args.retriever_threshold)
    retrived_narrative_memory = []
    for r in result:
        similar_task = r
        similar_experience = narrative_memory[r]
        retrived_narrative_memory.append({'task': similar_task, 'experience': similar_experience})
    logger.info(f"\033[32mRetrived narrative memory: {retrived_narrative_memory}\033[0m")

    # build the planner
    args.use_planner = True
    if args.use_planner:
        planner_llm = create_llm(args.provider, args.planner_model, args.planner_temperature)
        logger.info(f"\033[32m{args.planner_model} is used for planner.\033[0m")
    else:
        planner_llm = None
        logger.info(f"\033[32mPlanner is not used.\033[0m")

    # build browser agent
    agent_cls = getattr(sys.modules[__name__], args.browser_agent_module)
    browser_agent_llm = create_llm(args.provider, args.browser_agent_model)
    logger.info(f"\033[32mBrowser agent llm is {args.browser_agent_model}.\033[0m")

    # build the browser environment
    args.generate_gif = True
    if args.headless:
        is_headless = True
    else:
        is_headless = False
    browser_config = BrowserConfig(headless=False)
    browser = BrowserBugFix(browser_config)

    context_config = BrowserContextConfig(
        minimum_wait_page_load_time=0.5,
        browser_window_size={'width': args.viewport_width, 'height': args.viewport_height},
    )
    context = BrowserContextBugFix(browser=browser, config=context_config)

    # logging steup
    if args.generate_gif:
        save_gif_path = os.path.join(args.result_dir, args.task_id, "gifs")
        if not os.path.exists(save_gif_path):
            os.makedirs(save_gif_path, exist_ok=True)
        gif_file = os.path.join(save_gif_path, f"{task_id}.gif")
    else:
        gif_file = False

    # add custom actions
    credentials = LoginInCredentials(username=os.environ.get("SALESFORCE_USERNAME", ""),
                                     password=os.environ.get("SALESFORCE_PASSWORD", ""))
    assert credentials.username != "", "Please set the environment variable SALESFORCE_USERNAME"
    assert credentials.password != "", "Please set the environment variable SALESFORCE_PASSWORD"
    controller, initial_actions = get_login_controller_and_action(credentials)

    @controller.action(
        "Call external planner agent to revise the current plan. This action should be called when the browser agent feels getting stuck in a loop, cannot recover from the error, or is unable to make progress.",
        param_model=NoParamsAction)
    async def replan(param_model: NoParamsAction, browser: BrowserContextBugFix) -> ActionResult:
        return ActionResult(extracted_content="Re-plan signal received", include_in_memory=True)

    if agent_cls == AgentWithCustomPlanner:
        agent = agent_cls(
            task=rephrased_query,
            llm=browser_agent_llm,
            browser_context=context,
            initial_actions=initial_actions,
            controller=controller,
            generate_gif=gif_file,
            planner_llm=planner_llm,
            planner_interval=10000,  # encourage auto-replan
            planner_inputs={'retrieved_narrative_memory': retrived_narrative_memory, 'include_init_state_observation': False}
        )
    else:
        raise ValueError(f"Invalid browser agent module: {args.browser_agent_module}")

    args.max_steps = 50
    history, current_page = await agent.run(max_steps=args.max_steps)
    jsonfied_trajectory = agent.get_jsonfied_trajectory()
    trajectory_path = os.path.join(args.result_dir, args.task_id, "trajectory")
    if not os.path.exists(trajectory_path):
        os.makedirs(trajectory_path, exist_ok=True)

    agent_generated_trajectory_path = os.path.join(trajectory_path, f"{task_id}.json")
    with open(agent_generated_trajectory_path, 'w') as f:
        traj_data = {
            'task_prompt': agent.task,
            'is_successful': agent.state.history.is_successful(),
            'steps': jsonfied_trajectory
        }
        json.dump(traj_data, f, indent=4)

    browser_agent_usage = summarize_usage_info_from_jsonfied_trajectory(jsonfied_trajectory)

    trajectory_description = agent_trajectory_parser(agent_generated_trajectory_path)
    logger.info(f"\033[32mTrajectory description: {trajectory_description}.\033[0m")
    return browser_agent_usage, trajectory_description