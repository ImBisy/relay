"""
Email system tool - supports sending and drafting emails.
"""
import smtplib
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, Optional
from .base import BaseTool, ToolResult
from ..config.settings import config


class EmailTool(BaseTool):
    """
    Email tool for drafting and sending emails.
    
    Always requires confirmation before sending.
    Supports email aliases configured in settings.
    """
    
    name = "email"
    description = "Send or draft emails"
    requires_confirmation = True
    
    # Common email aliases
    DEFAULT_ALIASES = {
        "work": "Work Email",
        "personal": "Personal Email",
        "school": "School Email",
    }
    
    def __init__(self):
        self.pending_emails: Dict[str, Dict[str, Any]] = {}
    
    def execute(self, entities: Dict[str, Any]) -> ToolResult:
        """
        Execute email action.
        
        Flow:
        1. Validate entities
        2. If draft_only, save draft and return success
        3. Otherwise, prepare email and request confirmation
        4. On confirmation, send email
        """
        is_valid, error = self.validate(entities)
        if not is_valid:
            return ToolResult.failure(f"Invalid email request: {error}")
        
        # Check if draft only
        draft_only = entities.get('draft_only', False)
        
        # Resolve recipient
        recipient = self._resolve_recipient(entities)
        if not recipient:
            return ToolResult.failure("Could not determine recipient")
        
        # Build email content
        subject = entities.get('subject', '')
        body = entities.get('body', entities.get('content', ''))
        
        if not body:
            return ToolResult.failure("Email body is required")
        
        # Get sender account
        account_name = entities.get('account', 'default')
        account = self._get_account(account_name)
        
        if not account:
            return ToolResult.failure(f"Email account '{account_name}' not configured")
        
        # Build email data
        email_data = {
            'from': account['from_address'],
            'to': recipient,
            'subject': subject,
            'body': body,
            'account': account,
        }
        
        if draft_only:
            # Save as draft (implementation depends on storage system)
            draft_id = self._save_draft(email_data)
            return ToolResult.success(
                f"Email drafted. Subject: {subject or 'No subject'}",
                data={'draft_id': draft_id, 'recipient': recipient}
            )
        
        # Request confirmation before sending
        prompt = self.get_confirmation_prompt(entities) or f"Send to {recipient}?"
        
        # Store pending email for later confirmation
        email_id = self._generate_email_id()
        self.pending_emails[email_id] = email_data
        
        return ToolResult.needs_confirmation(
            "Email prepared.",
            prompt=prompt,
            data={
                'email_id': email_id,
                'recipient': recipient,
                'subject': subject or 'No subject',
                'preview': body[:100] + "..." if len(body) > 100 else body,
            }
        )
    
    def confirm_send(self, email_id: str) -> ToolResult:
        """Send a pending email after confirmation."""
        if email_id not in self.pending_emails:
            return ToolResult.failure("Email not found or already sent")
        
        email_data = self.pending_emails.pop(email_id)
        
        try:
            self._send_email_smtp(email_data)
            return ToolResult.success(
                f"Email sent to {email_data['to']}",
                data={'recipient': email_data['to']}
            )
        except Exception as e:
            return ToolResult.failure(
                "Failed to send email",
                error=str(e)
            )
    
    def cancel_send(self, email_id: str) -> ToolResult:
        """Cancel a pending email."""
        if email_id in self.pending_emails:
            del self.pending_emails[email_id]
            return ToolResult.success("Email cancelled")
        return ToolResult.failure("Email not found")
    
    def validate(self, entities: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate email entities."""
        # Must have either recipient_alias or recipient_email
        has_recipient = (
            entities.get('recipient_alias') or 
            entities.get('recipient_email') or
            entities.get('to')
        )
        
        if not has_recipient:
            return False, "Recipient required (email address or alias)"
        
        # Must have content
        has_content = (
            entities.get('body') or 
            entities.get('content') or
            entities.get('message')
        )
        
        if not has_content:
            return False, "Email body required"
        
        return True, None
    
    def get_confirmation_prompt(self, entities: Dict[str, Any]) -> str:
        """Generate confirmation prompt."""
        recipient = self._resolve_recipient(entities) or "unknown recipient"
        subject = entities.get('subject', '')
        
        if subject:
            return f"Send email '{subject}' to {recipient}?"
        return f"Send this email to {recipient}?"
    
    def _resolve_recipient(self, entities: Dict[str, Any]) -> Optional[str]:
        """Resolve recipient from entities."""
        # Direct email address
        if 'recipient_email' in entities:
            return entities['recipient_email']
        
        if 'to' in entities:
            email = entities['to']
            if re.match(r'\S+@\S+\.\S+', email):
                return email
        
        # Check alias
        alias = entities.get('recipient_alias', '').lower().strip()
        if alias:
            # Try to resolve alias to email from contacts/config
            resolved = self._resolve_alias(alias)
            if resolved:
                return resolved
        
        return None
    
    def _resolve_alias(self, alias: str) -> Optional[str]:
        """Resolve an alias to an email address."""
        # Check configured aliases
        aliases = config.email.accounts.get('aliases', {})
        
        # Normalize alias
        alias_lower = alias.lower().replace(' email', '').replace(' mail', '')
        
        # Check direct match
        if alias in aliases:
            return aliases[alias]
        
        # Check normalized match
        for key, email in aliases.items():
            if alias_lower in key.lower() or key.lower() in alias_lower:
                return email
        
        # Try default aliases
        if alias_lower in ['work', 'work email']:
            return aliases.get('work')
        if alias_lower in ['personal', 'personal email']:
            return aliases.get('personal')
        if alias_lower in ['school', 'school email', 'uni', 'university']:
            return aliases.get('school')
        
        return None
    
    def _get_account(self, account_name: str) -> Optional[Dict[str, Any]]:
        """Get email account configuration."""
        accounts = config.email.accounts
        
        if account_name in accounts:
            return accounts[account_name]
        
        # Return default if available
        if 'default' in accounts:
            return accounts['default']
        
        # Return first account
        if accounts:
            return next(iter(accounts.values()))
        
        return None
    
    def _send_email_smtp(self, email_data: Dict[str, Any]) -> None:
        """Send email via SMTP."""
        account = email_data['account']
        
        msg = MIMEMultipart()
        msg['From'] = email_data['from']
        msg['To'] = email_data['to']
        msg['Subject'] = email_data['subject']
        
        msg.attach(MIMEText(email_data['body'], 'plain'))
        
        with smtplib.SMTP(account['smtp_server'], account['smtp_port']) as server:
            server.starttls()
            server.login(account['username'], account['password'])
            server.send_message(msg)
    
    def _save_draft(self, email_data: Dict[str, Any]) -> str:
        """Save email as draft."""
        import json
        from datetime import datetime
        import hashlib
        
        draft_id = hashlib.md5(
            f"{email_data['to']}{datetime.now()}".encode()
        ).hexdigest()[:12]
        
        data_dir = config.get_data_dir()
        drafts_file = data_dir / "drafts.json"
        
        drafts = {}
        if drafts_file.exists():
            with open(drafts_file) as f:
                drafts = json.load(f)
        
        drafts[draft_id] = {
            **email_data,
            'created_at': datetime.now().isoformat(),
        }
        
        with open(drafts_file, 'w') as f:
            json.dump(drafts, f, indent=2)
        
        return draft_id
    
    def _generate_email_id(self) -> str:
        """Generate unique email ID."""
        import uuid
        return str(uuid.uuid4())[:8]
