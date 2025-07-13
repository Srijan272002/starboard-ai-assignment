'use client'

import { forwardRef } from 'react'
import { motion, type HTMLMotionProps } from 'framer-motion'
import { cn } from '@/lib/utils'

interface CardProps extends Omit<HTMLMotionProps<'div'>, 'ref'> {
  variant?: 'default' | 'bordered'
  isHoverable?: boolean
}

const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ className, variant = 'default', isHoverable = false, children, ...props }, ref) => {
    const baseStyles = 'rounded-lg bg-white dark:bg-gray-800'
    const variants = {
      default: 'shadow-lg',
      bordered: 'border border-gray-200 dark:border-gray-700',
    }
    const hoverStyles = isHoverable
      ? 'transition-transform duration-200 hover:-translate-y-1 hover:shadow-xl'
      : ''

    return (
      <motion.div
        ref={ref}
        className={cn(baseStyles, variants[variant], hoverStyles, className)}
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: 10 }}
        {...props}
      >
        {children}
      </motion.div>
    )
  }
)

Card.displayName = 'Card'

export { Card, type CardProps } 