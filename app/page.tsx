export default function HomePage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">Wedding WebApp</h1>
        <p className="text-gray-600 mb-8">Welcome to the Wedding Management System</p>
        <div className="space-x-4">
          <a 
            href="/admin/login" 
            className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700"
          >
            Admin Login
          </a>
        </div>
      </div>
    </div>
  );
}