import React, { useState } from 'react';
import { ShieldCheck, ShieldAlert, ChevronDown, Check, AlertTriangle, Info, AlertOctagon } from 'lucide-react';
import './AuditCenter.css';

export default function AuditCenter({ complianceData }) {
  const { issues = [], rules_evaluated = 0 } = complianceData || {};
  const [filter, setFilter] = useState('all');
  const [expandedIssues, setExpandedIssues] = useState({});

  const toggleExpand = (idx) => {
    setExpandedIssues(prev => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  // Helper count severity
  const countSeverity = (severity) => {
    return issues.filter(issue => issue.severity === severity).length;
  };

  const getFilteredIssues = () => {
    if (filter === 'all') return issues;
    return issues.filter(issue => issue.severity === filter);
  };

  const getSeverityIcon = (severity) => {
    switch (severity) {
      case 'critical':
        return <AlertOctagon size={18} style={{ color: 'var(--status-danger)' }} />;
      case 'major':
        return <AlertTriangle size={18} style={{ color: '#f97316' }} />;
      case 'minor':
        return <AlertTriangle size={18} style={{ color: 'var(--status-warning)' }} />;
      case 'warning':
      default:
        return <Info size={18} style={{ color: 'var(--status-info)' }} />;
    }
  };

  const filtered = getFilteredIssues();

  return (
    <div className="glass-panel audit-container animate-fade-in">
      <div className="audit-header">
        <h3 className="audit-title">
          <ShieldAlert size={22} style={{ color: issues.length > 0 ? 'var(--status-danger)' : 'var(--status-success)' }} />
          <span>Audit Log Checklist</span>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: '400' }}>
            ({rules_evaluated} rules evaluated)
          </span>
        </h3>

        <div className="filter-bar">
          <button 
            className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({issues.length})
          </button>
          <button 
            className={`filter-btn ${filter === 'critical' ? 'active critical' : ''}`}
            onClick={() => setFilter('critical')}
          >
            Critical ({countSeverity('critical')})
          </button>
          <button 
            className={`filter-btn ${filter === 'major' ? 'active major' : ''}`}
            onClick={() => setFilter('major')}
          >
            Major ({countSeverity('major')})
          </button>
          <button 
            className={`filter-btn ${filter === 'minor' ? 'active minor' : ''}`}
            onClick={() => setFilter('minor')}
          >
            Minor ({countSeverity('minor')})
          </button>
          <button 
            className={`filter-btn ${filter === 'warning' ? 'active warning' : ''}`}
            onClick={() => setFilter('warning')}
          >
            Warnings ({countSeverity('warning')})
          </button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="no-issues-box">
          <ShieldCheck size={48} style={{ marginBottom: '1rem' }} />
          <h4 style={{ fontFamily: 'var(--font-headings)', fontSize: '1.2rem', fontWeight: '700' }}>Perfect Compliance</h4>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginTop: '0.25rem', maxWidth: '300px' }}>
            No anomalies or errors found in the uploaded shipping documentation.
          </p>
        </div>
      ) : (
        <div className="issue-list">
          {filtered.map((issue, idx) => {
            const isExpanded = !!expandedIssues[idx];
            return (
              <div 
                key={idx} 
                className={`issue-card ${issue.severity} ${isExpanded ? 'expanded' : ''}`}
              >
                <button 
                  className="issue-trigger"
                  onClick={() => toggleExpand(idx)}
                >
                  <div className="issue-trigger-left">
                    {getSeverityIcon(issue.severity)}
                    <div className="issue-name-row">
                      <span className="issue-name">{issue.rule_name}</span>
                      <span className="issue-code">{issue.rule_id} • {issue.category.replace('_', ' ')}</span>
                    </div>
                  </div>
                  <div className="issue-trigger-right">
                    <span className={`deduction-badge ${issue.severity}`}>
                      {issue.deduction > 0 ? `-${issue.deduction} pts` : '0 pts'}
                    </span>
                    <ChevronDown size={18} className="expand-icon" />
                  </div>
                </button>

                {isExpanded && (
                  <div className="issue-details">
                    <p className="issue-desc">{issue.description}</p>
                    
                    <div className="issue-meta-grid">
                      <div className="issue-meta-item">
                        <span className="issue-meta-lbl">Affected Field</span>
                        <span className="issue-meta-val code">{issue.field}</span>
                      </div>
                      <div className="issue-meta-item">
                        <span className="issue-meta-lbl">Severity</span>
                        <span className="issue-meta-val" style={{ textTransform: 'capitalize' }}>
                          {issue.severity}
                        </span>
                      </div>
                    </div>

                    {(issue.found !== null || issue.expected !== null) && (
                      <div className="audit-compare-box">
                        <div className="compare-panel found">
                          <span className="compare-lbl">Found Value</span>
                          <span className="compare-val">{issue.found || 'Empty / Missing'}</span>
                        </div>
                        <div className="compare-panel expected">
                          <span className="compare-lbl">Expected / Standard</span>
                          <span className="compare-val">{issue.expected || 'Valid field criteria'}</span>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
