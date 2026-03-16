/**
 * DocumentUploadModal - Multi-step wizard for document upload and OCR review.
 *
 * Steps:
 * 1. Select - Choose file and document type
 * 2. Processing - Upload and OCR processing
 * 3. Review - Review and edit extracted data (OCRReviewStep)
 */
import React, { useState } from 'react';
import './DocumentUploadModal.css';
import { DocumentType, DocumentUploadResponse, OCRResult } from '../../types/inventory';
import { uploadDocument, getOCRResult, discardUploadedDocument } from '../../services/documents';
import OCRReviewStep from './OCRReviewStep';

type UploadStep = 'select' | 'processing' | 'review';

interface DocumentUploadModalProps {
  onClose: () => void;
  onSuccess: () => void;
}

const DocumentUploadModal: React.FC<DocumentUploadModalProps> = ({
  onClose,
  onSuccess
}) => {
  const [step, setStep] = useState<UploadStep>('select');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [documentType, setDocumentType] = useState<DocumentType>(DocumentType.BILL);
  const [isDragging, setIsDragging] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [ocrResult, setOcrResult] = useState<OCRResult | null>(null);
  const [isDiscarding, setIsDiscarding] = useState(false);

  // File validation
  const ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png'];
  const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

  const validateFile = (file: File): string | null => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      return 'Invalid file type. Only PDF, JPEG, and PNG files are allowed.';
    }
    if (file.size > MAX_FILE_SIZE) {
      return `File too large (${(file.size / 1024 / 1024).toFixed(2)} MB). Maximum size is 10 MB.`;
    }
    return null;
  };

  const handleFileSelect = (file: File) => {
    const validationError = validateFile(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    setSelectedFile(file);
    setError(null);
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) return;

    setStep('processing');
    setUploadProgress(20);
    setError(null);

    try {
      // Upload document
      setUploadProgress(40);
      const uploadResponse: DocumentUploadResponse = await uploadDocument(
        selectedFile,
        documentType
      );

      setUploadProgress(60);

      if (uploadResponse.status === 'failed') {
        throw new Error(uploadResponse.message || 'Upload failed');
      }

      // Get OCR result
      if (uploadResponse.ocr_result_id) {
        setUploadProgress(80);
        const result = await getOCRResult(uploadResponse.ocr_result_id);
        setOcrResult(result);
        setUploadProgress(100);

        // Move to review step
        setTimeout(() => {
          setStep('review');
        }, 500);
      } else {
        throw new Error('OCR result not available');
      }
    } catch (err: any) {
      setError(err.message || 'Upload failed. Please try again.');
      setStep('select');
      setUploadProgress(0);
    }
  };

  const handleReviewComplete = () => {
    onSuccess();
  };

  const handleCloseWithDiscard = async () => {
    if (step === 'review' && ocrResult?._id) {
      setIsDiscarding(true);
      try {
        await discardUploadedDocument(ocrResult._id);
      } catch {
        // Even if discard fails, allow closing to avoid trapping the user.
      } finally {
        setIsDiscarding(false);
      }
    }
    onClose();
  };

  const renderSelectStep = () => (
    <div className="upload-step-select">
      <h2>Upload Document</h2>
      <p className="step-description">
        Upload a Purchase Order or Bill/Invoice for automatic data extraction.
      </p>

      {/* Document Type Selection */}
      <div className="document-type-selector">
        <label>Document Type:</label>
        <div className="type-options">
          <button
            className={`type-option ${documentType === DocumentType.PO ? 'active' : ''}`}
            onClick={() => setDocumentType(DocumentType.PO)}
          >
            <span className="icon">📋</span>
            <span>Purchase Order</span>
          </button>
          <button
            className={`type-option ${documentType === DocumentType.BILL ? 'active' : ''}`}
            onClick={() => setDocumentType(DocumentType.BILL)}
          >
            <span className="icon">🧾</span>
            <span>Bill/Invoice</span>
          </button>
        </div>
      </div>

      {/* File Drop Zone */}
      <div
        className={`file-drop-zone ${isDragging ? 'dragging' : ''} ${selectedFile ? 'has-file' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleFileDrop}
        onClick={() => document.getElementById('file-input')?.click()}
      >
        <input
          id="file-input"
          type="file"
          accept=".pdf,.jpg,.jpeg,.png"
          onChange={handleFileInputChange}
          style={{ display: 'none' }}
        />

        {selectedFile ? (
          <div className="selected-file-info">
            <span className="file-icon">📄</span>
            <div className="file-details">
              <p className="file-name">{selectedFile.name}</p>
              <p className="file-size">
                {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>
            <button
              className="btn-remove-file"
              onClick={(e) => {
                e.stopPropagation();
                setSelectedFile(null);
              }}
            >
              ✕
            </button>
          </div>
        ) : (
          <div className="drop-zone-content">
            <span className="upload-icon">📤</span>
            <p className="drop-zone-text">
              Drag and drop file here, or click to browse
            </p>
            <p className="file-types-hint">
              Supported: PDF, JPEG, PNG (max 10 MB)
            </p>
          </div>
        )}
      </div>

      {error && <div className="error-message">{error}</div>}

      {/* Action Buttons */}
      <div className="modal-actions">
        <button className="btn-cancel" onClick={onClose}>
          Cancel
        </button>
        <button
          className="btn-upload"
          onClick={handleUpload}
          disabled={!selectedFile}
        >
          Upload & Process
        </button>
      </div>
    </div>
  );

  const renderProcessingStep = () => (
    <div className="upload-step-processing">
      <h2>Processing Document</h2>
      <p className="step-description">
        Extracting data from your document using OCR...
      </p>

      <div className="processing-animation">
        <div className="spinner"></div>
      </div>

      <div className="progress-bar">
        <div
          className="progress-fill"
          style={{ width: `${uploadProgress}%` }}
        ></div>
      </div>

      <p className="progress-text">{uploadProgress}% complete</p>

      <div className="processing-steps">
        <div className={`processing-step ${uploadProgress >= 20 ? 'complete' : ''}`}>
          <span className="step-icon">✓</span>
          <span>Uploading file</span>
        </div>
        <div className={`processing-step ${uploadProgress >= 60 ? 'complete' : ''}`}>
          <span className="step-icon">✓</span>
          <span>Extracting text</span>
        </div>
        <div className={`processing-step ${uploadProgress >= 80 ? 'complete' : ''}`}>
          <span className="step-icon">✓</span>
          <span>Parsing data</span>
        </div>
        <div className={`processing-step ${uploadProgress >= 100 ? 'complete' : ''}`}>
          <span className="step-icon">✓</span>
          <span>Matching items</span>
        </div>
      </div>
    </div>
  );

  const renderReviewStep = () => (
    <div className="upload-step-review">
      {ocrResult && (
        <OCRReviewStep
          ocrResult={ocrResult}
          onApprove={handleReviewComplete}
          onReject={handleReviewComplete}
        />
      )}
    </div>
  );

  return (
    <div className="document-upload-modal-overlay" onClick={handleCloseWithDiscard}>
      <div
        className="document-upload-modal"
        onClick={(e) => e.stopPropagation()}
      >
        {step === 'review' && (
          <button
            className="modal-close-btn"
            onClick={handleCloseWithDiscard}
            disabled={isDiscarding}
            aria-label="Close and discard upload"
          >
            {isDiscarding ? '...' : '✕'}
          </button>
        )}
        {step === 'select' && renderSelectStep()}
        {step === 'processing' && renderProcessingStep()}
        {step === 'review' && renderReviewStep()}
      </div>
    </div>
  );
};

export default DocumentUploadModal;
