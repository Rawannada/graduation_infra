import { useState, useEffect } from "react";

export default function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [recent, setRecent] = useState([]);
  const accessToken = localStorage.getItem("accessToken");

  // Fetch all files once on component mount (used as "recent")
  useEffect(() => {
    async function fetchRecent() {
      try {
        console.log("fetching recent...");
        const res = await fetch("http://localhost:3000/upload/recent", {
          headers: { Authorization: `bearer ${accessToken}` },
        });
        const data = await res.json();
        console.log("Recent response:", data);
        setRecent(data.files || []);
      } catch (err) {
        console.error(err);
      }
    }
    fetchRecent();
  }, []);

  // Handle search input (optional fetch from server for extra search)
  async function handleSearch(value) {
    setQuery(value);

    if (!value) {
      setResults([]);
      return;
    }

    try {
      console.log("Searching:", value);
      const res = await fetch(
        `http://localhost:3000/upload/search?search=${value}`,
        {
          method: "GET",
          headers: { Authorization: `bearer ${accessToken}` },
        },
      );
      const data = await res.json();
      console.log("Search data:", data);
      setResults(data.files || []);
    } catch (err) {
      console.error(err);
    }
  }

  // Extract filename from URL
  function getFileName(url) {
    return url.split("\\").pop().split("/").pop();
  }

  // Filter recent files based on query
  const filteredRecent = recent.filter((file) => {
    if (!query) return true; // show all if no search
    const fileName = getFileName(file.url).toLowerCase();
    return fileName.includes(query.toLowerCase());
  });

  return (
    <div className="search">
      <h2>Search</h2>

      <input
        type="text"
        placeholder="Search for files"
        value={query}
        onChange={(e) => handleSearch(e.target.value)}
      />

      {/* Recent Files */}
      <div className="recent">
        <span style={{ fontSize: "20px", fontWeight: "600" }}>Recent</span>
        {filteredRecent.length > 0 ? (
          filteredRecent.map((file, index) => {
            const fileName = file.name || getFileName(file.url);
            return (
              <div key={file.url || index} className="recent-item">
                <a
                  href={file.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ textDecoration: "none", color: "black" }}
                >
                  {fileName}
                </a>
              </div>
            );
          })
        ) : (
          <p>No files found</p>
        )}
      </div>

      {/* Optional Server Search Results */}
      {/* {results.length > 0 && (
        <div className="results">
          <h3>Results</h3>
          {results.map((file, index) => {
            const fileName = getFileName(file.url);
            return (
              <div key={file.url || index} className="result-item">
                <a
                  href={file.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ textDecoration: "none", color: "black" }}
                >
                  {fileName}
                </a>
              </div>
            );
          })}
        </div>
      )} */}
    </div>
  );
}
