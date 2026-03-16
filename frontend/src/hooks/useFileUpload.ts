/**
 * useFileUpload - Custom hook for handling file uploads with validation.
 */
import { useState } from 'react';

const ALLOWED_TYPES = ['application/pdf', 'image/jpeg', 'image/png'];
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 MB

interface UseFileUploadOptions {
  allowedTypes?: string[];
  maxFileSize?: number;
  onFileSelect?: (file: File) => void;
  onError?: (error: string) => void;
}

interface UseFileUploadReturn {
  selectedFile: File | null;
  error: string | null;
  isDragging: boolean;
  handleFileSelect: (file: File) => void;
  handleFileDrop: (e: React.DragEvent) => void;
  handleDragOver: (e: React.DragEvent) => void;
  handleDragLeave: () => void;
  handleFileInputChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  clearFile: () => void;
  clearError: () => void;
}

export const useFileUpload = (options: UseFileUploadOptions = {}): UseFileUploadReturn => {
  const {
    allowedTypes = ALLOWED_TYPES,
    maxFileSize = MAX_FILE_SIZE,
    onFileSelect,
    onError
  } = options;

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const validateFile = (file: File): string | null => {
    if (!allowedTypes.includes(file.type)) {
      const allowedExtensions = allowedTypes
        .map(type => type.split('/')[1].toUpperCase())
        .join(', ');
      return `Invalid file type. Allowed types: ${allowedExtensions}`;
    }

    if (file.size > maxFileSize) {
      const maxSizeMB = (maxFileSize / 1024 / 1024).toFixed(0);
      const fileSizeMB = (file.size / 1024 / 1024).toFixed(2);
      return `File too large (${fileSizeMB} MB). Maximum size is ${maxSizeMB} MB.`;
    }

    return null;
  };

  const handleFileSelect = (file: File) => {
    const validationError = validateFile(file);

    if (validationError) {
      setError(validationError);
      if (onError) {
        onError(validationError);
      }
      return;
    }

    setSelectedFile(file);
    setError(null);

    if (onFileSelect) {
      onFileSelect(file);
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const clearFile = () => {
    setSelectedFile(null);
    setError(null);
  };

  const clearError = () => {
    setError(null);
  };

  return {
    selectedFile,
    error,
    isDragging,
    handleFileSelect,
    handleFileDrop,
    handleDragOver,
    handleDragLeave,
    handleFileInputChange,
    clearFile,
    clearError
  };
};

export default useFileUpload;
