/** N — màn hình lỗi chung. */
import { Link } from 'react-router-dom'

export function ErrorPage({ message }: { message?: string }) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 p-6 text-center">
      <h1 className="text-3xl font-bold text-red-700">Đã có lỗi xảy ra</h1>
      <p className="text-base text-gray-600">
        {message ?? 'Hệ thống gặp sự cố không mong muốn. Vui lòng thử lại hoặc quay về bảng điều khiển.'}
      </p>
      <Link to="/" className="text-base text-blue-600 hover:underline">
        Quay về bảng điều khiển
      </Link>
    </div>
  )
}
