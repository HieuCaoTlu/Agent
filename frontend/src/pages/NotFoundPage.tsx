/** N — màn hình 404. */
import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 p-6 text-center">
      <h1 className="text-3xl font-bold text-gray-900">404</h1>
      <p className="text-base text-gray-600">Không tìm thấy trang bạn yêu cầu.</p>
      <Link to="/" className="text-base text-blue-600 hover:underline">
        Quay về bảng điều khiển
      </Link>
    </div>
  )
}
