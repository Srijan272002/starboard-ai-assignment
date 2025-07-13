'use client'
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { useState } from 'react';

const reportTypes = [
  {
    id: 'market-analysis',
    title: 'Market Analysis Report',
    description: 'Comprehensive analysis of market trends, pricing, and property values',
    format: 'PDF',
    file: 'market-analysis-report.pdf',
  },
  {
    id: 'property-comparison',
    title: 'Property Comparison Report',
    description: 'Detailed comparison of selected properties with key metrics',
    format: 'PDF',
    file: 'property-comparison-report.pdf',
  },
  {
    id: 'property-data',
    title: 'Property Data Export',
    description: 'Raw property data export including all available metrics',
    format: 'CSV',
    file: 'property-data-export.csv',
  },
  {
    id: 'investment-analysis',
    title: 'Investment Analysis Report',
    description: 'ROI calculations and investment potential analysis',
    format: 'PDF',
    file: 'investment-analysis-report.pdf',
  }
];

export default function ReportsPage() {
  const [modalOpen, setModalOpen] = useState(false);
  const [modalReport, setModalReport] = useState<{ title: string; format: string; file: string } | null>(null);

  const handleGenerate = (report: { title: string; format: string; file: string }) => {
    setModalReport(report);
    setModalOpen(true);
  };

  const handleClose = () => {
    setModalOpen(false);
    setModalReport(null);
  };

  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Reports & Exports</h1>
        <Button>View Export History</Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {reportTypes.map((report) => (
          <Card key={report.id} className="p-6">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-semibold mb-2">{report.title}</h2>
                <p className="text-gray-500 mb-4">{report.description}</p>
                <div className="flex items-center space-x-2 text-sm text-gray-500">
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.586 3H7a2 2 0 00-2 2v14a2 2 0 002 2z"
                    />
                  </svg>
                  <span>{report.format}</span>
                </div>
              </div>
              <Button variant="outline" onClick={() => handleGenerate(report)}>Generate Report</Button>
            </div>
          </Card>
        ))}
      </div>

      {/* Modal for mock report */}
      {modalOpen && modalReport && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-lg p-8 max-w-md w-full">
            <h2 className="text-2xl font-bold mb-4">{modalReport.title} Ready!</h2>
            <p className="mb-6">Your mock report is ready for download.</p>
            <a
              href={`/${modalReport.file}`}
              download
              className="inline-block bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 mb-4"
            >
              Download {modalReport.format}
            </a>
            <button
              onClick={handleClose}
              className="block w-full mt-2 px-4 py-2 bg-gray-200 dark:bg-gray-800 rounded hover:bg-gray-300 dark:hover:bg-gray-700"
            >
              Close
            </button>
          </div>
        </div>
      )}

      <Card className="mt-8 p-6">
        <h2 className="text-xl font-semibold mb-4">Scheduled Reports</h2>
        <div className="space-y-4">
          <div className="flex items-center justify-between py-3 border-b">
            <div>
              <div className="font-medium">Weekly Market Analysis</div>
              <div className="text-sm text-gray-500">Every Monday at 9:00 AM</div>
            </div>
            <div className="flex items-center space-x-4">
              <Button variant="outline" size="sm">Edit</Button>
              <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                Delete
              </Button>
            </div>
          </div>

          <div className="flex items-center justify-between py-3 border-b">
            <div>
              <div className="font-medium">Monthly Investment Report</div>
              <div className="text-sm text-gray-500">1st of every month</div>
            </div>
            <div className="flex items-center space-x-4">
              <Button variant="outline" size="sm">Edit</Button>
              <Button variant="outline" size="sm" className="text-red-600 hover:text-red-700">
                Delete
              </Button>
            </div>
          </div>
        </div>

        <div className="flex flex-col sm:flex-row gap-4 mt-4">
          <Button>Schedule New Report</Button>
          <a
            href="/scheduled-reports-export.csv"
            download
            className="inline-block bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 text-center"
            style={{ minWidth: '200px' }}
          >
            Download Scheduled Reports CSV
          </a>
        </div>
      </Card>
    </div>
  );
} 