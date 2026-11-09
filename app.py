"""BugForge AI: a Gemini-powered bug triage and action agent."""
import hmac
from html import escape
import os
import uuid
from pathlib import Path

import streamlit as st

from bugforge.agent import execute_plan
from bugforge.formatting import format_report
from bugforge.github_api import GitHubIssues, GitHubError
from bugforge.llm import analyze_bug, AnalysisError
from bugforge.store import TicketStore


st.set_page_config(page_title='BugForge AI | Game QA Agent', page_icon='🛠️', layout='wide')

st.markdown('''
<style>
.block-container { max-width: 1180px; padding-top: 1.9rem; }
.hero { padding: 1.8rem 2rem; border: 1px solid #334064;
        border-radius: 18px; background: linear-gradient(115deg,#202A52,#141B33 65%,#11172B); }
.hero h1 { font-size: 2.45rem; margin: 0 0 .4rem; font-weight: 800; letter-spacing: -.04em; }
.hero p { color: #CBD5EE; font-size: 1rem; max-width: 750px; margin: 0; }
.eyebrow { letter-spacing: .12em; font-size: .75rem; font-weight: 700; color: #A6B4FF; }
.kicker { font-size: .83rem; color: #9BAECC; }
.stage { padding: 14px 16px; border: 1px solid #333F63; border-radius: 12px; margin-bottom: .5rem; }
[data-testid="stMetric"] { border: 1px solid #303C5E; padding: 1rem; border-radius: 12px; }
</style>''', unsafe_allow_html=True)


def setting(name: str, default: str = '') -> str:
    value = os.environ.get(name)
    if value:
        return value
    try:
        return str(st.secrets.get(name, default))
    except (FileNotFoundError, KeyError):
        return default


if 'session_id' not in st.session_state:
    st.session_state.session_id = uuid.uuid4().hex
if 'runs' not in st.session_state:
    st.session_state.runs = 0

store = TicketStore(Path('.local') / st.session_state.session_id)
api_key = setting('GEMINI_API_KEY')
model = setting('GEMINI_MODEL', 'gemini-3.5-flash-lite')
repo = setting('GITHUB_REPO')
token = setting('GITHUB_TOKEN')
admin_pin = setting('ADMIN_PIN')
try:
    github = GitHubIssues(repo, token) if repo else None
except ValueError:
    github = None

with st.sidebar:
    st.markdown('### 🛠️ BugForge AI')
    st.caption('Agent settings and execution permissions')
    st.divider()
    st.markdown('**Gemini connection**')
    st.success('API key configured') if api_key else st.warning('Gemini key needed')
    st.caption(f'Model: `{model}`')
    st.markdown('**GitHub issue tracking**')
    if github and token:
        st.success(f'Repo: `{repo}`')
    elif github:
        st.info(f'Read-only: `{repo}`')
    else:
        st.info('Repository not configured')
    owner_pin = st.text_input('Owner PIN for publishing', type='password',
                              help='Only the owner should be able to publish issues using the app token.')
    authorized = bool(admin_pin and owner_pin and hmac.compare_digest(admin_pin, owner_pin))
    if authorized:
        st.caption('Owner publishing authorization granted for this session.')
    st.divider()
    st.caption('Security: tool allowlist · validated JSON · confirmation required · audit log')
    st.caption('Session data is temporary. Never submit confidential or unreleased game content.')

st.markdown('''<div class="hero"><div class="eyebrow">GEMINI-POWERED QA AUTOMATION</div>
<h1>BugForge AI</h1><p>From messy bug reports to structured QA tickets, reproducible test plans,
and real GitHub issues — with review and approval before execution.</p></div>''',
            unsafe_allow_html=True)
st.write('')

analysis_tab, tracker_tab, history_tab, how_tab = st.tabs(
    ['🔎 Investigate bug', '📋 Local tickets', '🛡️ Action history', 'ℹ️ How it works'])

with analysis_tab:
    st.markdown('### Describe the bug')
    st.caption('The description can include a request such as “save a report and create a local ticket” or “publish this issue on GitHub.”')
    if 'bug_prompt' not in st.session_state:
        st.session_state.bug_prompt = ''
    if st.button('Load demo scenario', help='Inserts a sample bug; Gemini still performs the analysis.'):
        st.session_state.bug_prompt = (
            'In my multiplayer game, after respawning I sometimes freeze for about five seconds '
            'if I switch weapons immediately. This happened 4 out of 5 attempts on Windows 11 '
            'build 0.9.7. I cannot move or shoot while frozen, but the game does not crash. '
            'Create a local QA ticket, save a Markdown report, and publish a GitHub issue.'
        )
        st.rerun()
    description = st.text_area('Observed behavior and requested actions', key='bug_prompt',
                               height=160, max_chars=4000,
                               placeholder='Describe what happened, what you expected, reproduction attempts, and what actions the agent should take...')
    col_project, col_env = st.columns(2)
    with col_project:
        project = st.text_input('Game or project', value='Demo Arena', max_chars=100)
    with col_env:
        environment = st.text_input('Platform and build', value='Windows 11 · Build 0.9.7', max_chars=250)

    analyze_disabled = not api_key or st.session_state.runs >= 8
    if st.button('Analyze with Gemini', type='primary', disabled=analyze_disabled, use_container_width=True):
        st.session_state.runs += 1
        st.session_state.pop('plan', None)
        st.session_state.pop('execution_results', None)
        st.session_state.pop('executed_plan_id', None)
        st.session_state.pop('duplicates', None)
        if not project.strip() or len(description.strip()) < 30:
            st.error('Provide a project name and a bug description of at least 30 characters.')
        else:
            with st.spinner('Gemini is creating the QA report and an actionable plan...'):
                try:
                    plan = analyze_bug(api_key, description, project.strip(), environment.strip(), model)
                    st.session_state.plan = plan
                    st.session_state.plan_id = uuid.uuid4().hex
                    st.session_state.plan_project = project.strip()
                    st.session_state.plan_environment = environment.strip()
                    store.log('gemini_analysis', 'SUCCESS', f'Created analysis: {plan.report.title}')
                    duplicates = store.find_similar(plan.report.title)
                    if github:
                        try:
                            duplicates += github.similar_issues(plan.report.title)
                        except GitHubError:
                            st.warning('GitHub duplicate search was unavailable. Local search still completed.')
                    st.session_state.duplicates = sorted(duplicates, key=lambda x: x['score'], reverse=True)[:5]
                except (AnalysisError, ValueError) as exc:
                    store.log('gemini_analysis', 'FAILED', str(exc))
                    st.error(str(exc))
    if not api_key:
        st.info('Add `GEMINI_API_KEY` to Streamlit secrets to enable live analysis. This app uses Google Gemini, not a local model.')
    if st.session_state.runs >= 8:
        st.warning('Session analysis limit reached. Start a new session for additional analyses.')

    if st.session_state.get('plan') is not None:
        plan = st.session_state.plan
        plan_project = st.session_state.plan_project
        plan_env = st.session_state.plan_environment
        markdown = format_report(plan.report, plan_project, plan_env)
        st.divider()
        st.markdown('### Gemini investigation')
        severity_col, type_col, tools_col = st.columns(3)
        severity_col.metric('Severity', plan.report.severity)
        type_col.metric('Category', plan.report.category)
        tools_col.metric('Requested actions', len(plan.actions))
        st.subheader(plan.report.title)
        st.write(plan.report.summary)
        st.caption(plan.explanation)
        with st.expander('Full QA report', expanded=True):
            st.markdown(markdown)
        st.download_button('Download proposed report (.md)', data=markdown.encode('utf-8'),
                           file_name='bugforge-review.md', mime='text/markdown')

        st.markdown('### Duplicate detection')
        duplicates = st.session_state.get('duplicates', [])
        if duplicates:
            for item in duplicates:
                st.warning(f"{item['score']:.0%} similar · {item['source']} · {item['title']}"
                           + (f" — {item['url']}" if item['url'] else ''))
            reviewed_duplicates = st.checkbox('I reviewed the possible duplicate issues.', key='review_duplicates')
        else:
            st.success('No close matches found among accessible local tickets and queried GitHub issues.')
            reviewed_duplicates = True

        st.markdown('### Proposed tool calls')
        if not plan.actions:
            st.info('Gemini selected analysis only. No external action is required for this request.')
        else:
            names = {a.name for a in plan.actions}
            for action in plan.actions:
                st.markdown(f'<div class="stage"><strong>{escape(action.name)}</strong><div class="kicker">{escape(action.reason)}</div></div>',
                            unsafe_allow_html=True)
            st.caption('Allowed: save_report writes an isolated Markdown file; create_ticket updates SQLite; publish_github_issue calls GitHub REST API.')
            publishing = 'publish_github_issue' in names
            if publishing and not github:
                st.error('Publishing requires GITHUB_REPO and GITHUB_TOKEN in secrets.')
            elif publishing and not token:
                st.error('Publishing requires a GitHub token.')
            elif publishing and not authorized:
                st.warning('GitHub publishing requires the owner PIN in the sidebar.')
            approved = st.checkbox('I reviewed these operations and authorize their execution.',
                                   key=f'approve_{st.session_state.plan_id}')
            can_execute = (approved and reviewed_duplicates and
                           (not publishing or (bool(github) and bool(token) and authorized)) and
                           st.session_state.get('executed_plan_id') != st.session_state.plan_id)
            if st.button('Execute approved actions', type='primary', disabled=not can_execute,
                         use_container_width=True):
                with st.spinner('Executing approved operations...'):
                    try:
                        st.session_state.execution_results = execute_plan(
                            plan, store, plan_project, plan_env, github, authorized, confirmed=True)
                        st.session_state.executed_plan_id = st.session_state.plan_id
                    except (PermissionError, ValueError) as exc:
                        st.error(str(exc))
            if st.session_state.get('executed_plan_id') == st.session_state.plan_id:
                st.markdown('### Execution results')
                for result in st.session_state.execution_results:
                    if result.status == 'SUCCESS':
                        st.success(f'{result.action}: {result.message}')
                        if result.url:
                            st.markdown(f'[Open new GitHub issue]({result.url})')
                    else:
                        st.error(f'{result.action}: {result.message}')

with tracker_tab:
    st.markdown('### Local issue tracker')
    tickets = store.list_tickets()
    if not tickets:
        st.info('No tickets created in this session yet. Submit and execute a create_ticket action.')
    else:
        st.dataframe([{'ID': t['id'], 'Title': t['title'], 'Severity': t['severity'],
                       'Category': t['category'], 'Project': t['project'],
                       'GitHub issue': t['github_url'] or 'Not published',
                       'Created (UTC)': t['created_at']} for t in tickets],
                     use_container_width=True, hide_index=True)
        for ticket in tickets:
            with st.expander(f"{ticket['id']} · {ticket['title']}"):
                from bugforge.models import BugReport
                report = BugReport.model_validate_json(ticket['report_json'])
                st.write(report.summary)
                st.caption(f"Severity: {report.severity} · Category: {report.category}")
                if ticket['report_file']:
                    path = store.reports / ticket['report_file']
                    if path.is_file():
                        st.download_button('Download saved report', path.read_bytes(),
                                           file_name=ticket['report_file'], key=f'download_{ticket["id"]}')
                if ticket['github_url']:
                    st.markdown(f"[Open GitHub issue]({ticket['github_url']})")

with history_tab:
    st.markdown('### Action audit trail')
    logs = store.list_audit()
    if not logs:
        st.info('No actions have been recorded in this session.')
    else:
        st.dataframe([{'Time (UTC)': item['created_at'], 'Operation': item['action'],
                       'Status': item['status'], 'Details': item['detail']}
                      for item in logs], use_container_width=True, hide_index=True)
    st.caption('The application logs successful and failed operations; it never executes model-generated shell commands.')

with how_tab:
    st.markdown('### How the agent makes decisions')
    st.markdown('''
1. **Input** — QA tester provides a game bug description and natural-language request.
2. **LLM integration** — Gemini returns a typed JSON report and proposed actions.
3. **Validation** — Pydantic enforces allowed action names and report structure.
4. **Safety** — Review, duplicate checks, owner PIN for GitHub, and explicit confirmation.
5. **Execution** — A narrow Python executor writes Markdown, inserts SQLite tickets, and creates GitHub issues.
6. **Audit** — Each action is logged with success or failure status.

**Prompt engineering:** Persona prompting, few-shot intent examples, structured response schema, and prompt-injection precautions.

**Limitations:** Proposed reproduction steps and root causes are hypotheses, not evidence that the game was tested. Local data is session-isolated and temporary on free cloud hosting. GitHub issues persist in the configured repository.
''')
