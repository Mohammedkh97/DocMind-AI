import React, { useState } from 'react';
import { FileText, ClipboardList, Code, Building2, Landmark, Ship, AlertCircle, Clock } from 'lucide-react';
import './DataViewer.css';

export default function DataViewer({ extractionData }) {
  const [activeTab, setActiveTab] = useState('invoice');
  const { invoice, packing_list, metadata } = extractionData || {};

  // Confidence helper
  const renderConfidence = (conf) => {
    if (conf === undefined || conf === null) return null;
    const score = Math.round(conf * 100);
    
    if (conf >= 0.85) {
      return <span className="conf-badge conf-high">{score}%</span>;
    }
    if (conf >= 0.60) {
      return <span className="conf-badge conf-medium">{score}%</span>;
    }
    return (
      <span className="conf-badge conf-low" title="Low confidence extraction. Please review!">
        <AlertCircle size={10} />
        {score}%
      </span>
    );
  };

  const renderFieldCard = (label, fieldObj) => {
    const value = fieldObj?.value;
    const confidence = fieldObj?.confidence;
    const isMissing = value === null || value === undefined || value === '';

    return (
      <div className="field-card">
        <div className="field-info">
          <span className="field-label">{label}</span>
          <span className={`field-value ${isMissing ? 'missing' : ''}`} title={isMissing ? 'Not Found' : String(value)}>
            {isMissing ? 'N/A' : String(value)}
          </span>
        </div>
        {!isMissing && renderConfidence(confidence)}
      </div>
    );
  };

  const formatCurrency = (amount, currencyField) => {
    if (amount === null || amount === undefined) return 'N/A';
    const currency = currencyField?.value || 'USD';
    try {
      return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(amount);
    } catch {
      return `${currency} ${amount}`;
    }
  };

  return (
    <div className="glass-panel dataviewer-container animate-fade-in">
      <div className="tabs-header">
        <button 
          className={`tab-btn ${activeTab === 'invoice' ? 'active' : ''}`} 
          onClick={() => setActiveTab('invoice')}
        >
          <FileText size={18} />
          <span>Commercial Invoice</span>
        </button>
        <button 
          className={`tab-btn ${activeTab === 'packing' ? 'active' : ''}`} 
          onClick={() => setActiveTab('packing')}
        >
          <ClipboardList size={18} />
          <span>Packing List</span>
        </button>
        <button 
          className={`tab-btn ${activeTab === 'json' ? 'active' : ''}`} 
          onClick={() => setActiveTab('json')}
        >
          <Code size={18} />
          <span>Raw API JSON</span>
        </button>
        <button 
          className={`tab-btn ${activeTab === 'performance' ? 'active' : ''}`} 
          onClick={() => setActiveTab('performance')}
        >
          <Clock size={18} />
          <span>Performance</span>
        </button>
      </div>

      <div className="tab-content">
        {/* --- INVOICE TAB --- */}
        {activeTab === 'invoice' && invoice && (
          <>
            {/* Header info */}
            <div className="details-section">
              <h4 className="section-title">Document Metadata</h4>
              <div className="fields-grid">
                {renderFieldCard('Invoice Number', invoice.invoice_number)}
                {renderFieldCard('Invoice Date', invoice.invoice_date)}
                {renderFieldCard('Payment Terms', invoice.payment_terms)}
                {renderFieldCard('Currency', invoice.currency)}
                {renderFieldCard('Port of Loading', invoice.port_of_loading)}
                {renderFieldCard('Port of Discharge', invoice.port_of_discharge)}
                {renderFieldCard('Incoterms', invoice.incoterms)}
                {renderFieldCard('L/C Number', invoice.lc_number)}
              </div>
            </div>

            {/* Seller & Buyer Grid */}
            <div className="grid-cols-2">
              <div className="details-section">
                <h4 className="section-title">
                  <Building2 size={16} />
                  <span>Seller (Shipper)</span>
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {renderFieldCard('Name', invoice.seller?.name)}
                  {renderFieldCard('Address', invoice.seller?.address)}
                  {renderFieldCard('Phone', invoice.seller?.phone)}
                  {renderFieldCard('VAT/Tax ID', invoice.seller?.vat_number)}
                </div>
              </div>
              <div className="details-section">
                <h4 className="section-title">
                  <Building2 size={16} />
                  <span>Buyer (Consignee)</span>
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {renderFieldCard('Name', invoice.buyer?.name)}
                  {renderFieldCard('Address', invoice.buyer?.address)}
                  {renderFieldCard('Phone', invoice.buyer?.phone)}
                  {renderFieldCard('TRN/Registration', invoice.buyer?.trn)}
                </div>
              </div>
            </div>

            {/* Shipment & Bank Grid */}
            <div className="grid-cols-2">
              <div className="details-section">
                <h4 className="section-title">
                  <Ship size={16} />
                  <span>Shipment Details</span>
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {renderFieldCard('Vessel Name', invoice.shipment?.vessel_name)}
                  {renderFieldCard('Port of Loading', invoice.shipment?.port_of_loading)}
                  {renderFieldCard('ETD', invoice.shipment?.etd)}
                </div>
              </div>
              <div className="details-section">
                <h4 className="section-title">
                  <Landmark size={16} />
                  <span>Bank & Payment Details</span>
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {renderFieldCard('Bank Name', invoice.bank_details?.bank_name)}
                  {renderFieldCard('Account Name', invoice.bank_details?.account_name)}
                  {renderFieldCard('Account #', invoice.bank_details?.account_number)}
                  {renderFieldCard('SWIFT Code', invoice.bank_details?.swift_code)}
                  {renderFieldCard('IBAN', invoice.bank_details?.iban)}
                </div>
              </div>
            </div>

            {/* Line Items */}
            <div className="details-section">
              <h4 className="section-title">Invoice Line Items</h4>
              <div className="table-wrapper">
                <table className="viewer-table">
                  <thead>
                    <tr>
                      <th style={{ width: '60px' }}>Item</th>
                      <th>Description</th>
                      <th style={{ width: '120px' }}>HS Code</th>
                      <th style={{ width: '100px' }}>Qty</th>
                      <th style={{ width: '80px' }}>Unit</th>
                      <th style={{ width: '120px' }}>Unit Price</th>
                      <th style={{ width: '140px' }}>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoice.line_items?.length > 0 ? (
                      invoice.line_items.map((item, idx) => (
                        <tr key={idx}>
                          <td>{item.item_no?.value || idx + 1}</td>
                          <td>
                            <div className="table-field-cell">
                              <span>{item.description?.value || 'N/A'}</span>
                              {renderConfidence(item.description?.confidence)}
                            </div>
                          </td>
                          <td>
                            <div className="table-field-cell">
                              <span>{item.hs_code?.value || 'N/A'}</span>
                              {renderConfidence(item.hs_code?.confidence)}
                            </div>
                          </td>
                          <td>
                            <div className="table-field-cell">
                              <span>{item.quantity?.value !== null ? item.quantity.value : 'N/A'}</span>
                              {renderConfidence(item.quantity?.confidence)}
                            </div>
                          </td>
                          <td>{item.unit?.value || 'N/A'}</td>
                          <td>
                            <div className="table-field-cell">
                              <span>{formatCurrency(item.unit_price?.value, invoice.currency)}</span>
                              {renderConfidence(item.unit_price?.confidence)}
                            </div>
                          </td>
                          <td>
                            <div className="table-field-cell">
                              <span style={{ fontWeight: '600' }}>
                                {formatCurrency(item.amount?.value, invoice.currency)}
                              </span>
                              {renderConfidence(item.amount?.confidence)}
                            </div>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="7" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                          No invoice line items found
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Financial Totals */}
            <div className="totals-box">
              <div className="total-row">
                <span>Subtotal:</span>
                <span style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  {formatCurrency(invoice.subtotal?.value, invoice.currency)}
                  {renderConfidence(invoice.subtotal?.confidence)}
                </span>
              </div>
              {invoice.freight?.value > 0 && (
                <div className="total-row">
                  <span>Freight Charges:</span>
                  <span style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    {formatCurrency(invoice.freight.value, invoice.currency)}
                    {renderConfidence(invoice.freight.confidence)}
                  </span>
                </div>
              )}
              {invoice.insurance?.value > 0 && (
                <div className="total-row">
                  <span>Insurance:</span>
                  <span style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    {formatCurrency(invoice.insurance.value, invoice.currency)}
                    {renderConfidence(invoice.insurance.confidence)}
                  </span>
                </div>
              )}
              <div className="total-row grand">
                <span>Grand Total:</span>
                <span style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  {formatCurrency(invoice.grand_total?.value, invoice.currency)}
                  {renderConfidence(invoice.grand_total?.confidence)}
                </span>
              </div>
            </div>
          </>
        )}

        {/* --- PACKING LIST TAB --- */}
        {activeTab === 'packing' && packing_list && (
          <>
            <div className="details-section">
              <h4 className="section-title">Document Metadata</h4>
              <div className="fields-grid">
                {renderFieldCard('Packing List Number', packing_list.packing_list_number)}
                {renderFieldCard('Reference Invoice', packing_list.ref_invoice)}
                {renderFieldCard('PL Date', packing_list.date)}
                {renderFieldCard('Total Cartons', packing_list.total_cartons)}
                {renderFieldCard('Total Net Weight (kg)', packing_list.total_net_weight)}
                {renderFieldCard('Total Gross Weight (kg)', packing_list.total_gross_weight)}
              </div>
            </div>

            {/* Line Items */}
            <div className="details-section">
              <h4 className="section-title">Packing List Line Items</h4>
              <div className="table-wrapper">
                <table className="viewer-table">
                  <thead>
                    <tr>
                      <th style={{ width: '60px' }}>Item</th>
                      <th>Description</th>
                      <th style={{ width: '100px' }}>Cartons</th>
                      <th style={{ width: '120px' }}>Quantity</th>
                      <th style={{ width: '80px' }}>Unit</th>
                      <th style={{ width: '150px' }}>Net Weight (KG)</th>
                      <th style={{ width: '150px' }}>Gross Weight (KG)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {packing_list.line_items?.length > 0 ? (
                      packing_list.line_items.map((item, idx) => (
                        <tr key={idx}>
                          <td>{item.item_no?.value || idx + 1}</td>
                          <td>
                            <div className="table-field-cell">
                              <span>{item.description?.value || 'N/A'}</span>
                              {renderConfidence(item.description?.confidence)}
                            </div>
                          </td>
                          <td>
                            <div className="table-field-cell">
                              <span>{item.cartons?.value !== null ? item.cartons.value : 'N/A'}</span>
                              {renderConfidence(item.cartons?.confidence)}
                            </div>
                          </td>
                          <td>
                            <div className="table-field-cell">
                              <span>{item.quantity?.value !== null ? item.quantity.value : 'N/A'}</span>
                              {renderConfidence(item.quantity?.confidence)}
                            </div>
                          </td>
                          <td>{item.unit?.value || 'N/A'}</td>
                          <td>
                            <div className="table-field-cell">
                              <span>{item.net_weight_kg?.value !== null ? item.net_weight_kg.value : 'N/A'}</span>
                              {renderConfidence(item.net_weight_kg?.confidence)}
                            </div>
                          </td>
                          <td>
                            <div className="table-field-cell">
                              <span>{item.gross_weight_kg?.value !== null ? item.gross_weight_kg.value : 'N/A'}</span>
                              {renderConfidence(item.gross_weight_kg?.confidence)}
                            </div>
                          </td>
                        </tr>
                      ))
                    ) : (
                      <tr>
                        <td colSpan="7" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                          No packing list line items found
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </>
        )}

        {/* --- RAW JSON TAB --- */}
        {activeTab === 'json' && (
          <div className="details-section">
            <h4 className="section-title">Raw Extraction Response</h4>
            <pre className="json-pre">
              {JSON.stringify(extractionData, null, 2)}
            </pre>
          </div>
        )}

        {/* --- PERFORMANCE TAB --- */}
        {activeTab === 'performance' && metadata && (
          <div className="details-section">
            <h4 className="section-title">Pipeline Execution Metrics</h4>
            <div className="grid-cols-2">
              <div className="field-card">
                <div className="field-info">
                  <span className="field-label">Total Processing Time</span>
                  <span className="field-value">{metadata.processing_time_seconds} s</span>
                </div>
              </div>
              <div className="field-card">
                <div className="field-info">
                  <span className="field-label">Primary Model</span>
                  <span className="field-value">{metadata.primary_model}</span>
                </div>
              </div>
              <div className="field-card">
                <div className="field-info">
                  <span className="field-label">Pages Processed</span>
                  <span className="field-value">{metadata.pages_processed}</span>
                </div>
              </div>
              <div className="field-card">
                <div className="field-info">
                  <span className="field-label">OCR Validation Used</span>
                  <span className="field-value">{metadata.ocr_validation_used ? 'Yes' : 'No'}</span>
                </div>
              </div>
            </div>

            <h4 className="section-title" style={{ marginTop: '1.5rem' }}>Step-by-Step Execution Times</h4>
            {metadata.execution_times ? (
              <div className="table-wrapper">
                <table className="viewer-table">
                  <thead>
                    <tr>
                      <th>Pipeline Stage</th>
                      <th style={{ width: '150px', textAlign: 'right' }}>Duration (Seconds)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(metadata.execution_times).map(([stage, duration]) => (
                      <tr key={stage}>
                        <td style={{ textTransform: 'capitalize' }}>{stage.replace('_', ' ')}</td>
                        <td style={{ textAlign: 'right', fontWeight: '600' }}>{duration} s</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)' }}>Execution times not available in this response.</div>
            )}
            
            {metadata.warnings?.length > 0 && (
              <>
                <h4 className="section-title" style={{ marginTop: '1.5rem', color: 'var(--status-warning)' }}>Pipeline Warnings</h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {metadata.warnings.map((warn, idx) => (
                    <div key={idx} style={{ padding: '0.75rem', background: 'rgba(234, 179, 8, 0.1)', borderLeft: '3px solid var(--status-warning)', borderRadius: '4px', fontSize: '0.85rem' }}>
                      {warn}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
