import json
from datetime import datetime, timezone
from app import db


class AnalysisHistory(db.Model):
    """Records every AI analysis call for cost tracking and caching."""
    __tablename__ = 'analysis_history'

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('applications.id'), nullable=False)

    analysis_type = db.Column(db.String(50), nullable=False)
    # critique | keywords | bullets | gap | tailor | interview | cover_letter

    _input_data = db.Column('input_data', db.Text)
    _output_data = db.Column('output_data', db.Text)

    tokens_used = db.Column(db.Integer, default=0)
    cost_usd = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    @property
    def input_data(self):
        return json.loads(self._input_data) if self._input_data else None

    @input_data.setter
    def input_data(self, value):
        self._input_data = json.dumps(value)

    @property
    def output_data(self):
        return json.loads(self._output_data) if self._output_data else None

    @output_data.setter
    def output_data(self, value):
        self._output_data = json.dumps(value)

    def to_dict(self):
        return {
            'id': self.id,
            'application_id': self.application_id,
            'analysis_type': self.analysis_type,
            'tokens_used': self.tokens_used,
            'cost_usd': round(self.cost_usd, 4),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
