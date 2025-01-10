import os

import mock
import pytest

from ddtrace.llmobs._evaluators.ragas.faithfulness import RagasFaithfulnessEvaluator
from ddtrace.span import Span
from tests.llmobs._utils import _expected_llmobs_llm_span_event
from tests.llmobs._utils import _expected_ragas_faithfulness_spans
from tests.llmobs._utils import _llm_span_with_expected_ragas_inputs_in_messages
from tests.llmobs._utils import _llm_span_with_expected_ragas_inputs_in_prompt


pytest.importorskip("ragas", reason="Tests require ragas to be available on user env")


def _llm_span_without_io():
    return _expected_llmobs_llm_span_event(Span("dummy"))


def test_ragas_evaluator_init(ragas, llmobs):
    rf_evaluator = RagasFaithfulnessEvaluator(llmobs)
    assert rf_evaluator.llmobs_service == llmobs
    assert rf_evaluator.ragas_faithfulness_instance == ragas.metrics.faithfulness
    assert rf_evaluator.ragas_faithfulness_instance.llm == ragas.llms.llm_factory()


def test_ragas_faithfulness_throws_if_dependencies_not_present(llmobs, mock_ragas_dependencies_not_present, ragas):
    with pytest.raises(NotImplementedError, match="Failed to load dependencies for `ragas_faithfulness` evaluator"):
        RagasFaithfulnessEvaluator(llmobs)


def test_ragas_faithfulness_returns_none_if_inputs_extraction_fails(ragas, mock_llmobs_submit_evaluation, llmobs):
    rf_evaluator = RagasFaithfulnessEvaluator(llmobs)
    failure_msg, _ = rf_evaluator.evaluate(_llm_span_without_io())
    assert failure_msg == "fail_extract_faithfulness_inputs"
    assert rf_evaluator.llmobs_service.submit_evaluation.call_count == 0


def test_ragas_faithfulness_has_modified_faithfulness_instance(
    ragas, mock_llmobs_submit_evaluation, reset_ragas_faithfulness_llm, llmobs
):
    """Faithfulness instance used in ragas evaluator should match the global ragas faithfulness instance"""
    from ragas.llms import BaseRagasLLM
    from ragas.metrics import faithfulness

    class FirstDummyLLM(BaseRagasLLM):
        def __init__(self):
            super().__init__()

        def generate_text(self) -> str:
            return "dummy llm"

        def agenerate_text(self) -> str:
            return "dummy llm"

    faithfulness.llm = FirstDummyLLM()

    rf_evaluator = RagasFaithfulnessEvaluator(llmobs)

    assert rf_evaluator.ragas_faithfulness_instance.llm.generate_text() == "dummy llm"

    class SecondDummyLLM(BaseRagasLLM):
        def __init__(self):
            super().__init__()

        def generate_text(self, statements) -> str:
            raise ValueError("dummy_llm")

        def agenerate_text(self, statements) -> str:
            raise ValueError("dummy_llm")

    faithfulness.llm = SecondDummyLLM()

    with pytest.raises(ValueError, match="dummy_llm"):
        rf_evaluator.evaluate(_llm_span_with_expected_ragas_inputs_in_prompt())


@pytest.mark.vcr_logs
def test_ragas_faithfulness_submits_evaluation(ragas, llmobs, mock_llmobs_submit_evaluation):
    """Test that evaluation is submitted for a valid llm span where question is in the prompt variables"""
    rf_evaluator = RagasFaithfulnessEvaluator(llmobs)
    llm_span = _llm_span_with_expected_ragas_inputs_in_prompt()
    rf_evaluator.run_and_submit_evaluation(llm_span)
    rf_evaluator.llmobs_service.submit_evaluation.assert_has_calls(
        [
            mock.call(
                span_context={
                    "span_id": llm_span.get("span_id"),
                    "trace_id": llm_span.get("trace_id"),
                },
                label=RagasFaithfulnessEvaluator.LABEL,
                metric_type=RagasFaithfulnessEvaluator.METRIC_TYPE,
                value=1.0,
                metadata={
                    "_dd.evaluation_span": {"span_id": mock.ANY, "trace_id": mock.ANY},
                    "_dd.faithfulness_disagreements": mock.ANY,
                    "_dd.evaluation_kind": "faithfulness",
                },
            )
        ]
    )


@pytest.mark.vcr_logs
def test_ragas_faithfulness_submits_evaluation_on_span_with_question_in_messages(
    ragas, llmobs, mock_llmobs_submit_evaluation
):
    """Test that evaluation is submitted for a valid llm span where the last message content is the question"""
    rf_evaluator = RagasFaithfulnessEvaluator(llmobs)
    llm_span = _llm_span_with_expected_ragas_inputs_in_messages()
    rf_evaluator.run_and_submit_evaluation(llm_span)
    rf_evaluator.llmobs_service.submit_evaluation.assert_has_calls(
        [
            mock.call(
                span_context={
                    "span_id": llm_span.get("span_id"),
                    "trace_id": llm_span.get("trace_id"),
                },
                label=RagasFaithfulnessEvaluator.LABEL,
                metric_type=RagasFaithfulnessEvaluator.METRIC_TYPE,
                value=1.0,
                metadata={
                    "_dd.evaluation_span": {"span_id": mock.ANY, "trace_id": mock.ANY},
                    "_dd.faithfulness_disagreements": mock.ANY,
                    "_dd.evaluation_kind": "faithfulness",
                },
            )
        ]
    )


@pytest.mark.vcr_logs
def test_ragas_faithfulness_submits_evaluation_on_span_with_custom_keys(ragas, llmobs, mock_llmobs_submit_evaluation):
    """Test that evaluation is submitted for a valid llm span where the last message content is the question"""
    rf_evaluator = RagasFaithfulnessEvaluator(llmobs)
    llm_span = _expected_llmobs_llm_span_event(
        Span("dummy"),
        prompt={
            "variables": {
                "user_input": "Is france part of europe?",
                "context_1": "hello, ",
                "context_2": "france is ",
                "context_3": "part of europe",
            },
            "_dd_context_variable_keys": ["context_1", "context_2", "context_3"],
            "_dd_query_variable_keys": ["user_input"],
        },
        output_messages=[{"content": "France is indeed part of europe"}],
    )
    rf_evaluator.run_and_submit_evaluation(llm_span)
    rf_evaluator.llmobs_service.submit_evaluation.assert_has_calls(
        [
            mock.call(
                span_context={
                    "span_id": llm_span.get("span_id"),
                    "trace_id": llm_span.get("trace_id"),
                },
                label=RagasFaithfulnessEvaluator.LABEL,
                metric_type=RagasFaithfulnessEvaluator.METRIC_TYPE,
                value=1.0,
                metadata={
                    "_dd.evaluation_span": {"span_id": mock.ANY, "trace_id": mock.ANY},
                    "_dd.faithfulness_disagreements": mock.ANY,
                    "_dd.evaluation_kind": "faithfulness",
                },
            )
        ]
    )


@pytest.mark.vcr_logs
def test_ragas_faithfulness_emits_traces(ragas, llmobs, llmobs_events):
    rf_evaluator = RagasFaithfulnessEvaluator(llmobs)
    rf_evaluator.evaluate(_llm_span_with_expected_ragas_inputs_in_prompt())
    ragas_spans = [event for event in llmobs_events if event["name"].startswith("dd-ragas.")]
    ragas_spans = sorted(ragas_spans, key=lambda d: d["start_ns"])
    assert len(ragas_spans) == 7
    # check name, io, span kinds match
    assert ragas_spans == _expected_ragas_faithfulness_spans()

    # verify the trace structure
    root_span = ragas_spans[0]
    root_span_id = root_span["span_id"]
    assert root_span["parent_id"] == "undefined"
    assert root_span["meta"] is not None
    assert root_span["meta"]["metadata"] is not None
    assert isinstance(root_span["meta"]["metadata"]["faithfulness_list"], list)
    assert isinstance(root_span["meta"]["metadata"]["statements"], list)
    root_span_trace_id = root_span["trace_id"]
    for child_span in ragas_spans[1:]:
        assert child_span["trace_id"] == root_span_trace_id

    assert ragas_spans[1]["parent_id"] == root_span_id  # input extraction (task)
    assert ragas_spans[2]["parent_id"] == root_span_id  # create statements (workflow)
    assert ragas_spans[4]["parent_id"] == root_span_id  # create verdicts (workflow)
    assert ragas_spans[6]["parent_id"] == root_span_id  # create score (task)
    assert ragas_spans[3]["parent_id"] == ragas_spans[2]["span_id"]  # create statements prompt (task)
    assert ragas_spans[5]["parent_id"] == ragas_spans[4]["span_id"]  # create verdicts prompt (task)


def test_llmobs_with_faithfulness_emits_traces_and_evals_on_exit(mock_writer_logs, run_python_code_in_subprocess):
    env = os.environ.copy()
    pypath = [os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))]
    if "PYTHONPATH" in env:
        pypath.append(env["PYTHONPATH"])
    env.update(
        {
            "PYTHONPATH": ":".join(pypath),
            "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", "dummy-openai-api-key"),
            "_DD_LLMOBS_EVALUATOR_INTERVAL": "5",
            "_DD_LLMOBS_EVALUATORS": "ragas_faithfulness",
            "DD_TRACE_ENABLED": "0",
        }
    )
    out, err, status, pid = run_python_code_in_subprocess(
        """
import os
import time
import atexit
import mock
from ddtrace.llmobs import LLMObs
from ddtrace.internal.utils.http import Response
from tests.llmobs._utils import _llm_span_with_expected_ragas_inputs_in_messages
from tests.llmobs._utils import logs_vcr

ctx = logs_vcr.use_cassette(
    "tests.llmobs.test_llmobs_ragas_evaluators.emits_traces_and_evaluations_on_exit.yaml"
)
ctx.__enter__()
atexit.register(lambda: ctx.__exit__())
with mock.patch("ddtrace.internal.writer.HTTPWriter._send_payload", return_value=Response(status=200, body="{}")):
    LLMObs.enable(api_key="dummy-api-key", site="datad0g.com", ml_app="unnamed-ml-app", agentless_enabled=True)
    LLMObs._instance._evaluator_runner.enqueue(_llm_span_with_expected_ragas_inputs_in_messages(), None)
    """,
        env=env,
    )
    assert status == 0, err
    assert out == b""
    assert err == b""