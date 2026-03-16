/**
 * DocumentsHistoryTab - Display document upload history.
 */
import React, { useState, useEffect } from 'react';
import './TabsCommon.css';
import { DocumentUpload, DocumentType, DocumentStatus, DocumentHistoryFilter } from '../../types/inventory';
import { getDocumentHistory, formatDate, getStatusColor, getStatusLabel } from '../../services/documents';

const DocumentsHistoryTab: React.FC = () => {
  const [documents, setDocuments] = useState<DocumentUpload[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [filters, setFilters] = useState<DocumentHistoryFilter>({});

  useEffect(() => {
    loadDocuments();
  }, [page, filters]);

  const loadDocuments = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await getDocumentHistory(page, 20, filters);
      setDocuments(response.data);
      setTotalPages(response.pagination.total_pages);
    } catch (err: any) {
      setError(err.message || 'Failed to load document history');
    } finally {
      setLoading(false);
    }
  };

  const handleFilterChange = (filterKey: keyof DocumentHistoryFilter, value: any) => {
    setFilters({ ...filters, [filterKey]: value });
    setPage(1);
  };

  const getFileIcon = (mimeType: string) => {
    if (mimeType === 'application/pdf') return '📄';
    if (mimeType.startsWith('image/')) return '🖼️';
    return '📁';
  };

  if (loading && documents.length === 0) {
    return <div className="loading-state">Loading document history...</div>;
  }

  if (error) {
    return <div className="error-state">Error: {error}</div>;
  }

  return (
    <div className="documents-history-tab">
      <div className="tab-header">
        <h2>Document Upload History</h2>
        <p className="tab-description">View all uploaded documents and their processing status</p>
      </div>

      {/* Filters */}
      <div className="filters-section">
        <select
          value={filters.document_type || ''}
          onChange={(e) => handleFilterChange('document_type', e.target.value || undefined)}
          className="filter-select"
        >
          <option value="">All Types</option>
          <option value={DocumentType.PO}>Purchase Orders</option>
          <option value={DocumentType.BILL}>Bills/Invoices</option>
        </select>

        <select
          value={filters.status || ''}
          onChange={(e) => handleFilterChange('status', e.target.value || undefined)}
          className="filter-select"
        >
          <option value="">All Statuses</option>
          <option value={DocumentStatus.UPLOADING}>Uploading</option>
          <option value={DocumentStatus.PROCESSING}>Processing</option>
          <option value={DocumentStatus.PENDING_REVIEW}>Pending Review</option>
          <option value={DocumentStatus.APPROVED}>Approved</option>
          <option value={DocumentStatus.REJECTED}>Rejected</option>
          <option value={DocumentStatus.FAILED}>Failed</option>
        </select>
      </div>

      {/* Document List */}
      {documents.length === 0 ? (
        <div className="empty-state">
          <p>No documents found</p>
        </div>
      ) : (
        <>
          <div className="documents-table-wrapper">
            <table className="documents-table">
              <thead>
                <tr>
                  <th>File</th>
                  <th>Type</th>
                  <th>Status</th>
                  <th>Uploaded</th>
                  <th>Uploaded By</th>
                </tr>
              </thead>
              <tbody>
                {documents.map((doc) => (
                  <tr key={doc._id}>
                    <td>
                      <div className="file-info">
                        <span className="file-icon">{getFileIcon(doc.mime_type)}</span>
                        <div className="file-details">
                          <span className="file-name">{doc.filename}</span>
                          {doc.error_message && (
                            <span className="error-hint" title={doc.error_message}>
                              ⚠️ {doc.error_message.substring(0, 50)}...
                            </span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="document-type-badge">
                        {doc.document_type === DocumentType.PO ? '📋 PO' : '🧾 Bill'}
                      </span>
                    </td>
                    <td>
                      <span className={`status-badge ${getStatusColor(doc.status)}`}>
                        {getStatusLabel(doc.status)}
                      </span>
                    </td>
                    <td>{formatDate(doc.created_at)}</td>
                    <td>{doc.uploaded_by_name || doc.uploaded_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="pagination">
              <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>
                Previous
              </button>
              <span>Page {page} of {totalPages}</span>
              <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}>
                Next
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default DocumentsHistoryTab;
