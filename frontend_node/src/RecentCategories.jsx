import React from "react";
import { useNavigate } from "react-router-dom";
import { EllipsisVertical } from "lucide-react";
import { useQuery } from "@tanstack/react-query";

export default function RecentCategories() {
  const navigate = useNavigate();

  function getBorderColor(index) {
    const colors = ["#FFE3E4", "#E3D2C0", "#BFD0FD", "#BCCABD"];
    return colors[index % colors.length];
  }

  async function fetchCategories() {
    const res = await fetch("/api/upload/categories", {
      headers: {
        Authorization: `bearer ${localStorage.getItem("accessToken")}`,
      },
    });

    if (!res.ok) {
      throw new Error("Failed to fetch categories");
    }

    const data = await res.json();

    return (data.categories || data).slice(-4).reverse();
  }

  const {
    data: categories = [],
    isLoading,
    error,
  } = useQuery({
  queryKey: ["recentCategories"],
  queryFn: fetchCategories,
  staleTime: 1000 * 60 * 5,
  gcTime: 1000 * 60 * 30,
  refetchOnWindowFocus: false,
  refetchOnMount: false,
});

  if (isLoading) {
    return <p>Loading...</p>;
  }

  if (error) {
    return <p>Error loading categories</p>;
  }

  return (
    <div className="recent-categories">
      <div className="recent-list">
        {categories.map((cat, index) => (
          <div
            key={cat._id}
            className="recent-card"
            onClick={() =>
              navigate(`/category-files/${cat._id}/${cat.categoryName}`)
            }
          >
            <div className="recent-card-nc">
              <div
                style={{
                  border: `3px solid ${getBorderColor(index)}`,
                }}
                className="code"
              >
                {cat.code}
              </div>

              <div className="name">{cat.categoryName}</div>
            </div>

            <EllipsisVertical size={17} />
          </div>
        ))}
      </div>
    </div>
  );
}