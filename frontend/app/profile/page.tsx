"use client";

export default function ProfilePage() {
  return (
    <div className="max-w-4xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Profile</h1>
      <div className="bg-gray-50 border rounded p-4 text-sm">
        <p className="font-medium">Authentication required</p>
        <p className="text-gray-600 mt-1">
          Sign in with GitHub or ORCID to view your profile, contribution
          history, and manage your curator/contributor role.
        </p>
      </div>
    </div>
  );
}
