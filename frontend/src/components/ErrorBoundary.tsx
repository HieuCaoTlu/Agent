/** N — bắt lỗi React runtime chưa xử lý, hiển thị ErrorPage thay vì màn hình trắng. */
import { Component, type ErrorInfo, type ReactNode } from 'react'

import { ErrorPage } from '@/pages/ErrorPage'

interface ErrorBoundaryState {
  error: Error | null
}

export class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('Lỗi runtime chưa xử lý:', error, info.componentStack)
  }

  render() {
    if (this.state.error) {
      return <ErrorPage message={this.state.error.message} />
    }
    return this.props.children
  }
}
