import glob
import json
import traceback
from collections import Counter
from scuba.helpers.utils import normalize_answer
from scuba.phases.base_phase import BasePhase
from scuba.phases.evaluation.retrieve_data_for_evaluation import DataRetriever
from scuba.phases.evaluation.milestone_evaluator_admin import MilestoneEvaluator as ME_admin
from scuba.phases.evaluation.milestone_evaluator_sales import MilestoneEvaluator as ME_sales
from scuba.phases.evaluation.milestone_evaluator_admin_new import MilestoneEvaluator as ME_admin_new
from scuba.phases.evaluation.milestone_evaluator_service import MilestoneEvaluator as ME_service

class ScoreCard():
    def __init__(self, score, milestones, system_failures):
        self.score = round(score, 2)
        self.milestones = milestones
        self.task_complete = self.score == 1
        self.system_failures = system_failures
        self.failure_reasons = self.convert_milestones_to_reasons()

    def convert_milestones_to_reasons(self):
        failure_reasons = []
        for milestone in self.milestones:
            if milestone['is_success'] == False:
                failure_reason = [f'Agent failed to {milestone["milestone"]}']
                failure_reasons.append(failure_reason)
        return failure_reasons

    def __dict__(self):
        return {
            'System Failiures': self.system_failures,
            'Score': self.score,
            'Task Complete': self.task_complete,
            'Failure Reasons': self.failure_reasons,
            'Rubric': self.milestones
        }


class MilestoneEvaluator(BasePhase):
    def __init__(self, org_alias):
        super().__init__(org_alias)
        self.data_retrieval_workflows = self.load_data_retrieval_workflows()
        self.evaluators = [ME_admin(org_alias), ME_sales(org_alias), ME_service(org_alias), ME_admin_new(org_alias)]

    def load_data_retrieval_workflows(self):
        data_retriever_workflows_json_pattern = 'scuba/phases/evaluation/evaluation_data_retrieval_workflows*'
        data_retriever_workflows_files = glob.glob(data_retriever_workflows_json_pattern)
        workflows = {}
        for file in data_retriever_workflows_files:
            workflows.update(json.load(open(file)))
        return workflows

    def get_evaluation_method(self, template_name):
        evaluation_method = []
        for evaluator in self.evaluators:
            method_name = 'evaluate_template_'+template_name
            if hasattr(evaluator, method_name):
                evaluation_method.append(getattr(evaluator, method_name))
        if len(evaluation_method) != 1:
            raise RuntimeError(f"The evaluation method for {template_name} is not defined or more than one is defined.")
        return evaluation_method[0]

    def f1_score(self, x, y):
        prediction_tokens = normalize_answer(y).split()
        ground_truth_tokens = normalize_answer(x).split()
        common = Counter(prediction_tokens) & Counter(ground_truth_tokens)
        num_same = sum(common.values())
        if num_same == 0:
            f1 = 0
        else:
            precision = 1.0 * num_same / len(prediction_tokens)
            recall = 1.0 * num_same / len(ground_truth_tokens)
            f1 = (2 * precision * recall) / (precision + recall)
        return f1

    def qa_evaluation(self, instance, agent_answer):
        ground_truth = instance['ground_truth_dict']['answer']
        f1 = self.f1_score(ground_truth, agent_answer)
        if ground_truth in agent_answer:
            score = f1
        else:
            score = 0
        milestones = [
            {
                'Milestone': f'Reply to the user with \'{ground_truth}\'',
                'is_success': True,
                'weight': score
            }
        ]
        return milestones

    def evaluate_instance(self, instance, agent_answer=None):
        query_template_name = instance['query_template_name']
        # since the eval is task agnostic, we need to check if the query_template_name starts with 'qa'
        if query_template_name.startswith('qa'):
            if agent_answer is None:
                raise ValueError("QA templates should have agent answer! But got None.")
            # if agent_answer is not None, we can evaluate the instance
            milestones = self.qa_evaluation(instance, agent_answer)
            score = sum(item['weight'] for item in milestones if item['is_success'])
            return ScoreCard(score, milestones, None)
        data_spec = self.data_retrieval_workflows.get(query_template_name)
        if not data_spec:
            raise RuntimeError(f"Data spec for {query_template_name} not found")

        try:
            retriever = DataRetriever(self.org_alias)
            ground_truth = instance['ground_truth_dict']
            data = retriever.retrieve_data(data_spec, ground_truth)

            evaluation_method = self.get_evaluation_method(query_template_name)
            milestones = evaluation_method(data, **ground_truth)
            score = sum(item['weight'] for item in milestones if item['is_success'])
            return ScoreCard(score, milestones, None)
        except Exception as e:
            failures = traceback.format_exc().splitlines()
            return ScoreCard(-1, [], failures)

