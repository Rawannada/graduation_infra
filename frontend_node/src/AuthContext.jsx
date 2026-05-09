import { createContext, useState, useEffect } from "react";

export const AuthContext = createContext();

export default function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem("accessToken"));

  // 🔥 sync token from login/logout events
  useEffect(() => {
    const handleAuthChange = () => {
      setToken(localStorage.getItem("accessToken"));
    };

    window.addEventListener("auth-change", handleAuthChange);

    return () =>
      window.removeEventListener("auth-change", handleAuthChange);
  }, []);

  // 🔥 fetch user whenever token changes
  useEffect(() => {
    const fetchUser = async () => {
      if (!token) {
        setUser(null);
        setLoading(false);
        return;
      }

      try {
        setLoading(true);

        const res = await fetch(
          "/api/users/profile",
          {
            headers: {
              Authorization: `bearer ${token}`,
            },
          }
        );

        if (!res.ok) throw new Error("Failed to fetch profile");

        const data = await res.json();
        setUser(data.user);
      } catch (err) {
        console.error(err);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    fetchUser();
  }, [token]);

  // 🔥 login helper (optional but useful)
  const login = (newToken) => {
    localStorage.setItem("accessToken", newToken);
    setToken(newToken);
    window.dispatchEvent(new Event("auth-change"));
  };

  // 🔥 logout helper
  const logout = () => {
    localStorage.removeItem("accessToken");
    setToken(null);
    setUser(null);
    window.dispatchEvent(new Event("auth-change"));
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        setUser,
        loading,
        token,
        setToken,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}