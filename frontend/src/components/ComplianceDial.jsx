import React, { useEffect, useState } from 'react';
import './ComplianceDial.css';

export default function ComplianceDial({ complianceData }) {
  const { score = 100, grade = 'A', total_issues = 0, critical_issues = 0, warnings = 0, summary = '' } = complianceData || {};
  const [animatedOffset, setAnimatedOffset] = useState(100);

  // SVG calculations for a radius=36 circle
  // circumference = 2 * pi * r = 2 * 3.14159 * 36 = 226.2
  const strokeDasharray = 226.2;
  
  useEffect(() => {
    // Animate the circle ring on load
    const scorePercent = Math.min(Math.max(score, 0), 100);
    const offset = strokeDasharray - (scorePercent / 100) * strokeDasharray;
    
    // Add small timeout for smooth browser rendering transition
    const timer = setTimeout(() => {
      setAnimatedOffset(offset);
    }, 100);
    
    return () => clearTimeout(timer);
  }, [score]);

  // Determine color theme class based on score
  const getThemeClass = () => {
    if (score >= 80) return 'theme-success';
    if (score >= 60) return 'theme-warning';
    return 'theme-danger';
  };

  const getGradeClass = () => {
    return `dial-grade grade-${grade.toLowerCase()}`;
  };

  return (
    <div className="glass-panel dial-container animate-fade-in">
      <h3 style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', marginBottom: '1.5rem', fontFamily: 'var(--font-headings)' }}>
        Customs Compliance Status
      </h3>
      
      <div className="svg-wrapper">
        <svg viewBox="0 0 80 80" className="circular-chart">
          <path
            className="circle-bg"
            d="M40 4
               a 36 36 0 1 1 0 72
               a 36 36 0 1 1 0 -72"
          />
          <path
            className={`circle ${getThemeClass()}`}
            strokeDasharray={`${strokeDasharray}`}
            strokeDashoffset={animatedOffset}
            d="M40 4
               a 36 36 0 1 1 0 72
               a 36 36 0 1 1 0 -72"
          />
        </svg>
        <div className="dial-hud">
          <div className="dial-score">{score}</div>
          <div className="dial-max">/ 100</div>
          <div className={getGradeClass()}>Grade {grade}</div>
        </div>
      </div>

      <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.4', margin: '0.5rem 0 1rem' }}>
        {summary}
      </p>

      <div className="metrics-summary">
        <div className="metric-item">
          <span className="metric-val" style={{ color: critical_issues > 0 ? 'var(--status-danger)' : 'var(--text-primary)' }}>
            {critical_issues}
          </span>
          <span className="metric-lbl">Critical</span>
        </div>
        <div className="metric-item">
          <span className="metric-val" style={{ color: 'var(--text-primary)' }}>
            {total_issues - critical_issues}
          </span>
          <span className="metric-lbl">Standard</span>
        </div>
        <div className="metric-item">
          <span className="metric-val" style={{ color: warnings > 0 ? 'var(--status-warning)' : 'var(--text-primary)' }}>
            {warnings}
          </span>
          <span className="metric-lbl">Warnings</span>
        </div>
      </div>
    </div>
  );
}
