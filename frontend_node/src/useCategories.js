import { useState, useEffect } from "react";

export function useCategories(accessToken) {
  const [categories, setCategories] = useState([]);

  useEffect(() => {
    async function fetchCategories() {
      try {
        const res = await fetch("http://localhost:3000/upload/categories", {
          headers: { Authorization: `bearer ${accessToken}` },
        });
        const data = await res.json();
        setCategories(data.categories || []);
      } catch (err) {
        console.error(err);
      }
    }
    if (accessToken) fetchCategories();
  }, [accessToken]);

  return { categories };
}
