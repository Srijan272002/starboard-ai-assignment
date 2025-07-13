'use client'

import { useRouter } from 'next/navigation'
import { Button } from '@/components/ui/Button'
import { Card } from '@/components/ui/Card'
import { motion } from 'framer-motion'

export default function Home() {
  const router = useRouter()

  const handleGetStarted = () => {
    router.push('/compare')
  }

  const handleLearnMore = () => {
    router.push('/compare')
  }

  return (
    <main className="min-h-screen">
      {/* Hero Section */}
      <section className="relative py-20 px-4 sm:px-6 lg:px-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mx-auto max-w-4xl text-center"
        >
          <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-6xl sm:leading-tight">
            Property Analytics Made Simple
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-gray-600 dark:text-gray-300">
            Get deep insights into property markets with advanced analytics and real-time data.
            Make informed decisions with our comprehensive property analysis platform.
          </p>
          <div className="mt-10 flex items-center justify-center gap-x-6">
            <Button size="lg" onClick={handleGetStarted}>
              Get Started
            </Button>
            <Button variant="outline" size="lg" onClick={handleLearnMore}>
              Learn More
            </Button>
          </div>
        </motion.div>
      </section>

      {/* Features Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gray-50 dark:bg-gray-900/50">
        <div className="mx-auto max-w-7xl">
          <h2 className="text-center text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl mb-16">
            Key Features
          </h2>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
            >
              <Card isHoverable className="h-full p-8">
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Market Analysis</h3>
                <p className="text-gray-600 dark:text-gray-300">
                  Deep dive into market trends with our advanced analytics tools.
                </p>
              </Card>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.2 }}
            >
              <Card isHoverable className="h-full p-8">
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Property Insights</h3>
                <p className="text-gray-600 dark:text-gray-300">
                  Get detailed property information and comparative analysis.
                </p>
              </Card>
            </motion.div>
            
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.3 }}
            >
              <Card isHoverable className="h-full p-8">
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Real-time Data</h3>
                <p className="text-gray-600 dark:text-gray-300">
                  Access up-to-date property data and market statistics.
                </p>
              </Card>
            </motion.div>
          </div>
        </div>
      </section>

      {/* How It Works Section */}
      <section className="py-20 px-4 sm:px-6 lg:px-8 bg-gray-50 dark:bg-gray-900/50">
        <div className="mx-auto max-w-7xl">
          <h2 className="text-center text-3xl font-bold tracking-tight text-gray-900 dark:text-white sm:text-4xl mb-16">
            How It Works
          </h2>
          <div className="grid gap-8 sm:grid-cols-2">
            <div className="flex flex-col items-center text-center">
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-primary text-primary-foreground text-2xl font-bold mb-4">1</div>
              <h3 className="text-xl font-semibold mb-2">Analyze Properties</h3>
              <p className="text-gray-600 dark:text-gray-300">Compare, analyze, and visualize property data and market trends.</p>
            </div>
            <div className="flex flex-col items-center text-center">
              <div className="flex items-center justify-center w-16 h-16 rounded-full bg-primary text-primary-foreground text-2xl font-bold mb-4">2</div>
              <h3 className="text-xl font-semibold mb-2">Make Decisions</h3>
              <p className="text-gray-600 dark:text-gray-300">Use insights to make smarter property investment decisions.</p>
            </div>
          </div>
        </div>
      </section>
    </main>
  )
}
