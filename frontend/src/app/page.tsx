import Link from 'next/link'
import {
  ChartBarIcon,
  BuildingOfficeIcon,
  DocumentCheckIcon,
  EnvelopeIcon,
  MapIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline'

const modules = [
  {
    name: 'Dashboard',
    description: 'Executive overview of deals, pipeline, and metrics',
    href: '/dashboard',
    icon: ChartBarIcon,
    color: 'bg-blue-500',
  },
  {
    name: 'CRM',
    description: 'Owners, parks, leads, and deal pipeline',
    href: '/crm',
    icon: BuildingOfficeIcon,
    color: 'bg-green-500',
  },
  {
    name: 'Parcels & Overlay',
    description: 'Search parcels with zoning, 311, adjudication overlays',
    href: '/parcels',
    icon: MapIcon,
    color: 'bg-purple-500',
  },
  {
    name: 'Financial Screening',
    description: 'DSCR, IRR, scenarios, and buy-box evaluation',
    href: '/financial',
    icon: ClipboardDocumentListIcon,
    color: 'bg-yellow-500',
  },
  {
    name: 'Due Diligence',
    description: 'Checklists, risk scoring, and document management',
    href: '/dd',
    icon: DocumentCheckIcon,
    color: 'bg-red-500',
  },
  {
    name: 'Campaigns',
    description: 'Direct mail and heir sourcing campaigns',
    href: '/campaigns',
    icon: EnvelopeIcon,
    color: 'bg-indigo-500',
  },
]

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-gray-900 mb-4">
            GallagherMHP Command
          </h1>
          <p className="text-xl text-gray-600 max-w-3xl mx-auto">
            AI-Assisted CRM + Deal Flow + Financial Screening + DD Suite for
            acquiring and operating 20+ unit mobile home parks in East Baton Rouge
          </p>
          <div className="mt-6 flex justify-center space-x-4">
            <div className="px-4 py-2 bg-green-100 text-green-800 rounded-full text-sm font-medium">
              Live EBR Data
            </div>
            <div className="px-4 py-2 bg-blue-100 text-blue-800 rounded-full text-sm font-medium">
              Production Ready
            </div>
            <div className="px-4 py-2 bg-purple-100 text-purple-800 rounded-full text-sm font-medium">
              2025 Edition
            </div>
          </div>
        </div>

        {/* Module Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {modules.map((module) => (
            <Link
              key={module.name}
              href={module.href}
              className="group relative bg-white rounded-xl shadow-sm border border-gray-200 p-6 hover:shadow-lg hover:border-primary-300 transition-all duration-200"
            >
              <div className="flex items-center mb-4">
                <div className={`${module.color} p-3 rounded-lg`}>
                  <module.icon className="h-6 w-6 text-white" />
                </div>
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2 group-hover:text-primary-600">
                {module.name}
              </h3>
              <p className="text-sm text-gray-600">{module.description}</p>
              <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                <svg
                  className="w-5 h-5 text-primary-600"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 5l7 7-7 7"
                  />
                </svg>
              </div>
            </Link>
          ))}
        </div>

        {/* Data Sources */}
        <div className="mt-16 card">
          <h2 className="text-2xl font-bold text-gray-900 mb-4">
            Live Data Sources
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 mt-1">
                <div className="h-2 w-2 bg-green-500 rounded-full"></div>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">
                  Socrata SODA v2 API
                </h3>
                <p className="text-sm text-gray-600">
                  EBR Property Information (re5c-hrw9) - Parcels, owners, addresses
                </p>
              </div>
            </div>
            <div className="flex items-start space-x-3">
              <div className="flex-shrink-0 mt-1">
                <div className="h-2 w-2 bg-green-500 rounded-full"></div>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">ArcGIS REST API</h3>
                <p className="text-sm text-gray-600">
                  EBRGIS - Tax parcels, zoning, city limits, 311 requests
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Quick Links */}
        <div className="mt-8 flex justify-center space-x-4">
          <Link
            href="/api/docs"
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            API Documentation →
          </Link>
          <Link
            href="/data-health"
            className="text-sm text-primary-600 hover:text-primary-700 font-medium"
          >
            Data Health →
          </Link>
        </div>
      </div>
    </div>
  )
}

