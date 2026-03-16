/**
 * OCRReviewStep - Review and edit OCR extracted data before approval.
 *
 * Features:
 * - Display extracted header fields (editable)
 * - Show matched items (green background)
 * - Show unmatched items with mapping dropdown (yellow background)
 * - Display warnings and price variances
 * - Approve or reject with notes
 */
import React, { useState, useEffect } from 'react';
import './OCRReviewStep.css';
import {
  OCRResult,
  ExtractedItem,
  MatchStatus,
  OCRApprovalRequest
} from '../../types/inventory';
import { approveOCRResult, rejectOCRResult, saveOCRAsPending, formatCurrency } from '../../services/documents';
import { inventoryService } from '../../services/inventory';
import { getErrorMessage } from '../../services/api';
import type { InventoryItem } from '../../types/inventory';

interface OCRReviewStepProps {
  ocrResult: OCRResult;
  onApprove: () => void;
  onReject: () => void;
}

const OCRReviewStep: React.FC<OCRReviewStepProps> = ({
  ocrResult,
  onApprove,
  onReject
}) => {
  const [editedFields, setEditedFields] = useState(ocrResult.extracted_fields);
  const [editedItems, setEditedItems] = useState<ExtractedItem[]>(ocrResult.extracted_items);
  const [reviewNotes, setReviewNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [inventoryItems, setInventoryItems] = useState<InventoryItem[]>([]);
  const [showRejectModal, setShowRejectModal] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  useEffect(() => {
    loadInventory();
  }, []);

  const loadInventory = async () => {
    try {
      const pageSize = 100; // Backend API max limit
      let page = 1;
      let totalPages = 1;
      const allItems: InventoryItem[] = [];

      do {
        const response = await inventoryService.getAllItems(page, pageSize);
        allItems.push(...response.data);
        totalPages = response.pagination?.total_pages || 1;
        page += 1;
      } while (page <= totalPages);

      setInventoryItems(allItems);
    } catch (err) {
      console.error('Failed to load inventory:', err);
    }
  };

  const handleFieldEdit = (fieldName: string, value: any) => {
    setEditedFields({
      ...editedFields,
      [fieldName]: value
    });
  };

  const handleItemEdit = (index: number, field: keyof ExtractedItem, value: any) => {
    const newItems = [...editedItems];
    newItems[index] = {
      ...newItems[index],
      [field]: value
    };
    setEditedItems(newItems);
  };

  const toNumberOr = (value: unknown, fallback: number): number => {
    const num = typeof value === 'number' ? value : Number(value);
    return Number.isFinite(num) ? num : fallback;
  };

  const buildSanitizedRequest = (): OCRApprovalRequest => {
    const sanitizedItems: ExtractedItem[] = editedItems.map((item) => {
      const quantity = toNumberOr(item.quantity, 0);
      const unitCostInr = Math.round(toNumberOr(item.unit_cost_inr, 0));
      const lineTotalInr = Math.round(
        toNumberOr(item.line_total_inr, quantity * unitCostInr)
      );
      const confidenceScore = toNumberOr(item.confidence_score, 0);

      return {
        ...item,
        quantity,
        unit_cost_inr: unitCostInr,
        line_total_inr: lineTotalInr,
        confidence_score: confidenceScore
      };
    });

    const sanitizedFields = { ...editedFields };
    if (sanitizedFields.total_amount_inr !== undefined) {
      sanitizedFields.total_amount_inr = Math.round(
        toNumberOr(sanitizedFields.total_amount_inr, 0)
      );
    }

    return {
      extracted_fields: sanitizedFields,
      extracted_items: sanitizedItems,
      review_notes: reviewNotes
    };
  };

  const handleItemMapping = (index: number, inventoryId: string) => {
    const newItems = [...editedItems];
    const selectedInventory = inventoryItems.find(item => item._id === inventoryId);

    if (selectedInventory) {
      newItems[index] = {
        ...newItems[index],
        matched_inventory_id: inventoryId,
        match_status: MatchStatus.EXACT,
        material_name: selectedInventory.material_name,
        unit: selectedInventory.unit
      };
    }

    setEditedItems(newItems);
  };

  const handleApprove = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      // Validate that all items are either matched or explicitly skipped
      const unmappedItems = editedItems.filter(
        item => item.match_status === MatchStatus.UNMATCHED && !item.notes?.includes('SKIP')
      );

      if (unmappedItems.length > 0) {
        setError(`${unmappedItems.length} items are not mapped. Please map or mark them to skip.`);
        setIsSubmitting(false);
        return;
      }

      const request = buildSanitizedRequest();

      await approveOCRResult(ocrResult._id, request);
      onApprove();
    } catch (err: any) {
      setError(getErrorMessage(err) || 'Failed to approve OCR result');
      setIsSubmitting(false);
    }
  };

  const handleReject = async () => {
    if (!rejectReason.trim()) {
      setError('Please provide a reason for rejection');
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      await rejectOCRResult(ocrResult._id, { reason: rejectReason });
      onReject();
    } catch (err: any) {
      setError(getErrorMessage(err) || 'Failed to reject OCR result');
      setIsSubmitting(false);
    }
  };

  const handleSavePending = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      const request = buildSanitizedRequest();
      await saveOCRAsPending(ocrResult._id, request);
      onApprove();
    } catch (err: any) {
      setError(getErrorMessage(err) || 'Failed to save pending review');
      setIsSubmitting(false);
    }
  };

  const matchedItemsCount = editedItems.filter(
    item => item.match_status === MatchStatus.EXACT
  ).length;

  const unmatchedItemsCount = editedItems.filter(
    item => item.match_status === MatchStatus.UNMATCHED
  ).length;

  return (
    <div className="ocr-review-step">
      <div className="review-header">
        <h2>Review Extracted Data</h2>
        <p className="review-subtitle">
          Review and edit the extracted information before approval
        </p>
      </div>

      {/* Warnings */}
      {ocrResult.warnings.length > 0 && (
        <div className="warnings-section">
          <h3>⚠️ Warnings</h3>
          <ul>
            {ocrResult.warnings.map((warning, index) => (
              <li key={index}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Document Info */}
      <div className="document-info-section">
        <h3>Document Information</h3>
        <div className="info-grid">
          <div className="info-field">
            <label>
              {ocrResult.document_type === 'PO' ? 'PO Number' : 'Invoice Number'}
            </label>
            <input
              type="text"
              value={editedFields.po_number || editedFields.invoice_number || ''}
              onChange={(e) =>
                handleFieldEdit(
                  ocrResult.document_type === 'PO' ? 'po_number' : 'invoice_number',
                  e.target.value
                )
              }
            />
          </div>

          <div className="info-field">
            <label>Date</label>
            <input
              type="date"
              value={editedFields.po_date || editedFields.invoice_date || ''}
              onChange={(e) =>
                handleFieldEdit(
                  ocrResult.document_type === 'PO' ? 'po_date' : 'invoice_date',
                  e.target.value
                )
              }
            />
          </div>

          {ocrResult.document_type === 'PO' && (
            <div className="info-field">
              <label>Expected Delivery Date</label>
              <input
                type="date"
                value={editedFields.expected_delivery_date || ''}
                onChange={(e) => handleFieldEdit('expected_delivery_date', e.target.value)}
              />
            </div>
          )}

          <div className="info-field">
            <label>Total Amount</label>
            <input
              type="number"
              value={toNumberOr(editedFields.total_amount_inr, 0) / 100}
              onChange={(e) =>
                handleFieldEdit('total_amount_inr', toNumberOr(e.target.value, 0) * 100)
              }
              step="0.01"
            />
          </div>
        </div>
      </div>

      {/* Items Summary */}
      <div className="items-summary">
        <span className="summary-badge success">
          {matchedItemsCount} Matched
        </span>
        <span className="summary-badge warning">
          {unmatchedItemsCount} Unmatched
        </span>
      </div>

      {/* Extracted Items Table */}
      <div className="items-section">
        <h3>Line Items</h3>
        <div className="items-table-wrapper">
          <table className="items-table">
            <thead>
              <tr>
                <th>Item Name</th>
                <th>Quantity</th>
                <th>Unit</th>
                <th>Unit Cost (₹)</th>
                <th>Confidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {editedItems.map((item, index) => (
                <tr
                  key={index}
                  className={
                    item.match_status === MatchStatus.EXACT ? 'matched' : 'unmatched'
                  }
                >
                  <td>
                    {item.match_status === MatchStatus.UNMATCHED ? (
                      <select
                        value={item.matched_inventory_id || ''}
                        onChange={(e) => handleItemMapping(index, e.target.value)}
                        className="item-mapping-select"
                      >
                        <option value="">-- Map to inventory --</option>
                        {inventoryItems.map(invItem => (
                          <option key={invItem._id} value={invItem._id}>
                            {invItem.material_name} ({invItem.material_id})
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span>{item.material_name}</span>
                    )}
                  </td>
                  <td>
                    <input
                      type="number"
                      value={toNumberOr(item.quantity, 0)}
                      onChange={(e) =>
                        handleItemEdit(index, 'quantity', toNumberOr(e.target.value, 0))
                      }
                      className="editable-field"
                      step="0.01"
                    />
                  </td>
                  <td>{item.unit}</td>
                  <td>
                    <input
                      type="number"
                      value={toNumberOr(item.unit_cost_inr, 0) / 100}
                      onChange={(e) =>
                        handleItemEdit(
                          index,
                          'unit_cost_inr',
                          toNumberOr(e.target.value, 0) * 100
                        )
                      }
                      className="editable-field"
                      step="0.01"
                    />
                  </td>
                  <td>
                    <span
                      className={`confidence-badge ${
                        item.confidence_score >= 0.9
                          ? 'high'
                          : item.confidence_score >= 0.7
                          ? 'medium'
                          : 'low'
                      }`}
                    >
                      {(item.confidence_score * 100).toFixed(0)}%
                    </span>
                  </td>
                  <td>
                    <span
                      className={`status-badge ${
                        item.match_status === MatchStatus.EXACT ? 'matched' : 'unmatched'
                      }`}
                    >
                      {item.match_status === MatchStatus.EXACT ? '✓ Matched' : '⚠ Unmatched'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Review Notes */}
      <div className="notes-section">
        <label htmlFor="review-notes">Review Notes (Optional)</label>
        <textarea
          id="review-notes"
          value={reviewNotes}
          onChange={(e) => setReviewNotes(e.target.value)}
          placeholder="Add any notes about this document..."
          rows={3}
        />
      </div>

      {/* Error Message */}
      {error && <div className="error-message">{error}</div>}

      {/* Action Buttons */}
      <div className="review-actions">
        <button
          className="btn-reject"
          onClick={() => setShowRejectModal(true)}
          disabled={isSubmitting}
        >
          Reject
        </button>
        <button
          className="btn-save-pending"
          onClick={handleSavePending}
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Saving...' : 'Save as Pending'}
        </button>
        <button
          className="btn-approve"
          onClick={handleApprove}
          disabled={isSubmitting}
        >
          {isSubmitting ? 'Processing...' : 'Approve & Update Inventory'}
        </button>
      </div>

      {/* Reject Modal */}
      {showRejectModal && (
        <div className="reject-modal-overlay" onClick={() => setShowRejectModal(false)}>
          <div className="reject-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Reject Document</h3>
            <p>Please provide a reason for rejecting this document:</p>
            <textarea
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="Reason for rejection..."
              rows={4}
              autoFocus
            />
            <div className="reject-modal-actions">
              <button onClick={() => setShowRejectModal(false)}>Cancel</button>
              <button onClick={handleReject} disabled={isSubmitting}>
                Confirm Reject
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default OCRReviewStep;
