"""The only allowed action executor. No shell commands or arbitrary paths."""
from dataclasses import dataclass
from .formatting import format_report
from .models import AgentPlan
from .store import TicketStore
from .github_api import GitHubIssues

ACTION_ORDER = ('save_report', 'create_ticket', 'publish_github_issue')


@dataclass
class ExecutionResult:
    action: str
    status: str
    message: str
    url: str = ''


def execute_plan(plan: AgentPlan, store: TicketStore, project: str, environment: str,
                 github: GitHubIssues | None, allow_publish: bool,
                 confirmed: bool) -> list[ExecutionResult]:
    if not confirmed:
        raise PermissionError('Explicit confirmation is required before executing any action.')
    selected = {action.name for action in plan.actions}
    if 'publish_github_issue' in selected and not allow_publish:
        raise PermissionError('GitHub publishing requires owner authorization.')
    if 'publish_github_issue' in selected and github is None:
        raise PermissionError('GitHub repository is not configured.')

    markdown = format_report(plan.report, project, environment)
    ticket_id = None
    file_name = None
    results = []
    for action in ACTION_ORDER:
        if action not in selected:
            continue
        try:
            if action == 'save_report':
                file_name = store.save_markdown(markdown)
                if ticket_id:
                    store.update_ticket(ticket_id, report_file=file_name)
                result = ExecutionResult(action, 'SUCCESS', f'Saved {file_name}')
            elif action == 'create_ticket':
                ticket_id = store.create_ticket(plan.report, project, report_file=file_name)
                result = ExecutionResult(action, 'SUCCESS', f'Created local ticket {ticket_id}')
            elif action == 'publish_github_issue':
                url = github.create_issue(f'[Bug] {plan.report.title}', markdown)
                if ticket_id:
                    store.update_ticket(ticket_id, github_url=url)
                result = ExecutionResult(action, 'SUCCESS', 'Published GitHub issue', url=url)
            store.log(action, result.status, result.message + (f' {result.url}' if result.url else ''))
            results.append(result)
        except Exception as exc:
            message = str(exc)[:400] or 'Action failed.'
            store.log(action, 'FAILED', message)
            results.append(ExecutionResult(action, 'FAILED', message))
            break
    return results
