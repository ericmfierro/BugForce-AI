from pathlib import Path
from unittest.mock import Mock
import pytest
from pydantic import ValidationError
from bugforge.models import AgentPlan, BugReport, ActionRequest
from bugforge.agent import execute_plan
from bugforge.store import TicketStore, similarity
from bugforge.github_api import GitHubIssues


def example_report():
    return BugReport(
        title='Player frozen after respawn weapon switch',
        summary='The player is unable to move or shoot for five seconds after respawning and switching weapons.',
        category='Gameplay', severity='High',
        severity_reason='Player loses movement and combat control for several seconds.',
        steps_to_reproduce=['Respawn in a multiplayer match', 'Immediately switch weapons'],
        expected_behavior='Movement and weapon controls remain responsive.',
        actual_behavior='Movement and attacks stop responding for five seconds.',
        possible_cause='Possible weapon transition state conflict; unverified.',
        suggested_tests=['Repeat with different weapon types', 'Compare against prior build'],
        tags=['respawn', 'weapon-switch'])


def make_plan(*names):
    return AgentPlan(report=example_report(), explanation='Analysis complete with proposed QA actions.',
                     actions=[ActionRequest(name=name, reason='Requested in user message') for name in names])


def test_unknown_action_rejected():
    with pytest.raises(ValidationError):
        ActionRequest(name='run_shell', reason='This should be blocked')


def test_duplicate_action_rejected():
    with pytest.raises(ValidationError):
        make_plan('save_report', 'save_report')


def test_confirmation_required(tmp_path):
    store = TicketStore(tmp_path)
    with pytest.raises(PermissionError):
        execute_plan(make_plan('save_report'), store, 'Arena', 'Windows', None, False, False)
    assert not list(store.reports.iterdir())


def test_execute_local_actions_and_audit(tmp_path):
    store = TicketStore(tmp_path)
    result = execute_plan(make_plan('create_ticket', 'save_report'), store,
                          'Arena', 'Windows', None, False, True)
    assert [x.status for x in result] == ['SUCCESS', 'SUCCESS']
    tickets = store.list_tickets()
    assert len(tickets) == 1
    assert tickets[0]['report_file']
    text = (store.reports / tickets[0]['report_file']).read_text()
    assert 'Suggested steps to reproduce' in text
    assert len(store.list_audit()) == 2


def test_publish_requires_owner_permission(tmp_path):
    store = TicketStore(tmp_path)
    github = Mock()
    with pytest.raises(PermissionError):
        execute_plan(make_plan('publish_github_issue'), store, 'Arena', 'Win', github, False, True)
    github.create_issue.assert_not_called()


def test_publish_calls_github_adapter(tmp_path):
    store = TicketStore(tmp_path)
    github = Mock()
    github.create_issue.return_value = 'https://github.com/demo/bugs/issues/2'
    results = execute_plan(make_plan('create_ticket', 'publish_github_issue'),
                           store, 'Arena', 'Windows', github, True, True)
    assert len(results) == 2
    assert results[-1].url == 'https://github.com/demo/bugs/issues/2'
    assert store.list_tickets()[0]['github_url'] == results[-1].url


def test_similar_titles():
    assert similarity('Freezes after respawn', 'Freezes after respawn') == 1
    assert similarity('Missing button', 'Server crashes on launch') < 0.63


def test_invalid_github_repo():
    with pytest.raises(ValueError):
        GitHubIssues('http://evil.example/other')


def test_report_path_generated_in_workspace(tmp_path):
    store = TicketStore(tmp_path)
    filename = store.save_markdown('# Safe report')
    assert '..' not in filename
    assert (store.reports / filename).is_file()


def test_github_error_logged_without_failing_local_work(tmp_path):
    store = TicketStore(tmp_path)
    github = Mock()
    github.create_issue.side_effect = RuntimeError('Service unavailable')
    result = execute_plan(make_plan('create_ticket', 'publish_github_issue'),
                          store, 'Arena', 'Windows', github, True, True)
    assert result[0].status == 'SUCCESS'
    assert result[1].status == 'FAILED'
    assert store.list_audit()[0]['status'] == 'FAILED'
