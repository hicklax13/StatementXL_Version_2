import React, { useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { X, ZoomIn, ZoomOut, ChevronLeft, ChevronRight } from 'lucide-react';
import type { ExtractedTable } from '../api/client';

// Configure pdfjs worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PDFOverlayProps {
    fileUrl: string;
    tables: ExtractedTable[];
    onClose: () => void;
}

export const PDFOverlay: React.FC<PDFOverlayProps> = ({ fileUrl, tables, onClose }) => {
    const [numPages, setNumPages] = useState<number>(0);
    const [pageNumber, setPageNumber] = useState<number>(1);
    const [scale, setScale] = useState<number>(1.2);

    // Track page loading status
    const [isPageLoaded, setIsPageLoaded] = useState(false);

    function onDocumentLoadSuccess({ numPages }: { numPages: number }) {
        setNumPages(numPages);
    }

    // Filter cells for the current page
    const currentCells = tables
        .filter(t => t.page === pageNumber)
        .flatMap(t => t.rows.flatMap(r => r.cells))
        .filter(c => c.bbox);

    // BBox format: [x0, y0, x1, y1] in PDF points (72 DPI)
    // React-PDF renders at 72DPI * scale.
    // So we need to scale the bbox coordinates.

    // Note: PDF origin is usually bottom-left for traditional PDF tools,
    // but pdfplumber usually returns top-left origin (or converting to it).
    // pdfplumber: (x0, top, x1, bottom).
    // React-PDF: renders top-down.

    return (
        <div className="fixed inset-0 z-50 bg-gray-900 bg-opacity-95 flex flex-col">
            {/* Header */}
            <div className="bg-white p-4 flex justify-between items-center shadow-md">
                <div className="flex items-center gap-4">
                    <h2 className="text-lg font-bold">PDF Overlay Verification</h2>
                    <div className="flex items-center space-x-2 bg-gray-100 rounded p-1">
                        <button
                            onClick={() => setPageNumber(prev => Math.max(prev - 1, 1))}
                            disabled={pageNumber <= 1}
                            className="p-1 hover:bg-gray-200 rounded disabled:opacity-50"
                        >
                            <ChevronLeft size={20} />
                        </button>
                        <span className="font-medium text-sm">
                            Page {pageNumber} of {numPages}
                        </span>
                        <button
                            onClick={() => setPageNumber(prev => Math.min(prev + 1, numPages))}
                            disabled={pageNumber >= numPages}
                            className="p-1 hover:bg-gray-200 rounded disabled:opacity-50"
                        >
                            <ChevronRight size={20} />
                        </button>
                    </div>
                </div>

                <div className="flex items-center gap-4">
                    <div className="flex items-center space-x-2">
                        <button onClick={() => setScale(s => Math.max(0.5, s - 0.2))} className="p-2 hover:bg-gray-100 rounded">
                            <ZoomOut size={20} />
                        </button>
                        <span className="text-sm font-medium">{Math.round(scale * 100)}%</span>
                        <button onClick={() => setScale(s => Math.min(3, s + 0.2))} className="p-2 hover:bg-gray-100 rounded">
                            <ZoomIn size={20} />
                        </button>
                    </div>

                    <button onClick={onClose} className="p-2 hover:bg-red-100 text-red-600 rounded">
                        <X size={24} />
                    </button>
                </div>
            </div>

            {/* PDF Viewer */}
            <div className="flex-1 overflow-auto flex justify-center p-8 relative">
                <div className="relative shadow-lg">
                    <Document
                        file={fileUrl}
                        onLoadSuccess={onDocumentLoadSuccess}
                        className="border border-gray-200"
                    >
                        <Page
                            pageNumber={pageNumber}
                            scale={scale}
                            onLoadSuccess={() => setIsPageLoaded(true)}
                            renderTextLayer={false}
                            renderAnnotationLayer={false}
                        />

                        {/* Overlay Layer */}
                        {isPageLoaded && (
                            <div className="absolute top-0 left-0 w-full h-full pointer-events-none">
                                {currentCells.map((cell, idx) => {
                                    if (!cell.bbox) return null;
                                    const [x0, top, x1, bottom] = cell.bbox;

                                    // Scale coordinates
                                    const left = x0 * scale;
                                    const t = top * scale;
                                    const width = (x1 - x0) * scale;
                                    const height = (bottom - top) * scale;

                                    return (
                                        <div
                                            key={`${idx}-${cell.value}`}
                                            className="absolute border pointer-events-auto group"
                                            style={{
                                                left: `${left}px`,
                                                top: `${t}px`,
                                                width: `${width}px`,
                                                height: `${height}px`,
                                                borderColor: cell.confidence > 0.8 ? 'rgba(34, 197, 94, 0.6)' : 'rgba(239, 68, 68, 0.6)',
                                                backgroundColor: cell.confidence > 0.8 ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                                            }}
                                        >
                                            {/* Tooltip */}
                                            <div className="hidden group-hover:block absolute bottom-full left-0 mb-1 z-50 min-w-[200px] bg-gray-900 text-white text-xs rounded p-2 shadow-xl">
                                                <p className="font-bold border-b border-gray-700 pb-1 mb-1">
                                                    Extracted Value
                                                </p>
                                                <p className="mb-1">{cell.value}</p>
                                                <p className="text-gray-400">Confidence: {(cell.confidence * 100).toFixed(0)}%</p>
                                                {cell.reasoning && (
                                                    <div className="mt-2 border-t border-gray-700 pt-1">
                                                        <p className="font-bold text-gray-400">Reasoning:</p>
                                                        <p className="italic">{cell.reasoning}</p>
                                                    </div>
                                                )}
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </Document>
                </div>
            </div>
        </div>
    );
};
