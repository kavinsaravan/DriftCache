"""
Agent Report Formatter

Generates human-readable reports for supervisor workflows
"""
from typing import Dict, Any, List
from datetime import datetime


class AgentReportFormatter:
    """
    Formats supervisor workflow results into readable reports
    """

    @staticmethod
    def format_supervisor_report(supervisor_result: Dict[str, Any]) -> str:
        """
        Generate comprehensive supervisor report

        Args:
            supervisor_result: Supervisor workflow result

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 80)
        report.append("DRIFTCACHE AUTONOMOUS INFRASTRUCTURE REPORT")
        report.append("=" * 80)
        report.append("")

        # Header
        report.append(f"Run ID: {supervisor_result.get('run_id')}")
        report.append(f"Trigger: {supervisor_result.get('trigger_reason')}")
        report.append(f"Started: {supervisor_result.get('started_at')}")
        report.append(f"Completed: {supervisor_result.get('completed_at')}")
        report.append("")

        # Diagnosis
        report.append("DIAGNOSIS")
        report.append("-" * 80)
        report.append(f"Issue: {supervisor_result.get('diagnosis')}")
        diagnosis_details = supervisor_result.get('diagnosis_details', '')
        if diagnosis_details:
            report.append(f"Details: {diagnosis_details}")
        report.append("")

        # Initial State
        initial = supervisor_result.get('initial_state', {})
        report.append("INITIAL SYSTEM STATE")
        report.append("-" * 80)
        report.append(f"Drift Severity: {initial.get('drift_severity', 'N/A')}")
        report.append(f"Precision: {initial.get('precision', 0):.1%}")
        report.append(f"Recall: {initial.get('recall', 0):.1%}")
        report.append(f"False Hit Rate: {initial.get('false_hit_rate', 0):.1%}")
        report.append(f"Cache Hit Rate: {initial.get('cache_hit_rate', 0):.1%}")
        report.append("")

        # Actions Taken
        actions = supervisor_result.get('actions_taken', [])
        report.append("ACTIONS TAKEN")
        report.append("-" * 80)
        if actions:
            for i, action in enumerate(actions, 1):
                report.append(f"{i}. {action.get('agent', 'unknown').upper()}")
                report.append(f"   Action: {action.get('action')}")
                report.append(f"   Reason: {action.get('reason')}")
                if action.get('result'):
                    report.append(f"   Result: {action.get('result_summary', 'Completed')}")
                report.append("")
        else:
            report.append("No actions required - system healthy")
            report.append("")

        # Validation
        validation = supervisor_result.get('validation', {})
        report.append("VALIDATION")
        report.append("-" * 80)
        report.append(f"Status: {validation.get('passed', 'N/A')}")
        improvements = validation.get('details', {}).get('improvements', [])
        if improvements:
            report.append("Improvements:")
            for imp in improvements:
                report.append(f"   {imp}")
        degradations = validation.get('details', {}).get('degradations', [])
        if degradations:
            report.append("Concerns:")
            for deg in degradations:
                report.append(f"  -> {deg}")
        report.append("")

        # Final State
        final = supervisor_result.get('final_state', {})
        report.append("FINAL SYSTEM STATE")
        report.append("-" * 80)
        report.append(f"Precision: {final.get('precision', 0):.1%}")
        report.append(f"Recall: {final.get('recall', 0):.1%}")
        report.append(f"False Hit Rate: {final.get('false_hit_rate', 0):.1%}")
        report.append("")

        # Status
        report.append("STATUS")
        report.append("-" * 80)
        report.append(f"Final Status: {supervisor_result.get('final_status', 'unknown').upper()}")
        report.append(f"Reason: {supervisor_result.get('status_reason', 'N/A')}")
        report.append("")

        # Recommendations
        recommendations = supervisor_result.get('recommendations', [])
        if recommendations:
            report.append("RECOMMENDATIONS")
            report.append("-" * 80)
            for rec in recommendations:
                report.append(f"  - {rec}")
            report.append("")

        report.append("=" * 80)

        return "\n".join(report)

    @staticmethod
    def format_summary(supervisor_result: Dict[str, Any]) -> str:
        """
        Generate short summary for dashboard

        Args:
            supervisor_result: Supervisor workflow result

        Returns:
            Brief summary string
        """
        diagnosis = supervisor_result.get('diagnosis')
        final_status = supervisor_result.get('final_status')
        actions_count = len(supervisor_result.get('actions_taken', []))

        return f"{diagnosis} -> {actions_count} action(s) -> {final_status}"
