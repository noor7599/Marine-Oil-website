import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Lock, Mail, Eye, EyeOff, Droplets, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const Login = () => {
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [showRegister, setShowRegister] = useState(false);

  // const API_URL = import.meta.env.VITE_API_URL || "http://localhost:5000";

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`/api/auth/login`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        setError(data.message || "Login failed. Please try again.");
        setLoading(false);
        return;
      }

      // Store token in localStorage
      localStorage.setItem("authToken", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));

      // Redirect to dashboard
      navigate("/dashboard");
    } catch (err) {
      setError("Connection error. Please check if the backend is running.");
      console.error("Login error:", err);
      setLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch(`/api/auth/register`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email: email.trim(),
          password,
        }),
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        setError(data.message || "Registration failed. Please try again.");
        setLoading(false);
        return;
      }

      // Store token in localStorage
      localStorage.setItem("authToken", data.token);
      localStorage.setItem("user", JSON.stringify(data.user));

      // Redirect to dashboard
      navigate("/dashboard");
    } catch (err) {
      setError("Connection error. Please check if the backend is running.");
      console.error("Registration error:", err);
      setLoading(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    if (showRegister) {
      handleRegister(e);
    } else {
      handleLogin(e);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center relative overflow-hidden">
      {/* Background */}
      <div className="absolute inset-0 ocean-gradient" />
      <div
        className="absolute inset-0 opacity-[0.04]"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1440 320'%3E%3Cpath fill='%23e0e1dd' d='M0,160L48,170.7C96,181,192,203,288,186.7C384,171,480,117,576,117.3C672,117,768,171,864,176C960,181,1056,139,1152,128C1248,117,1344,139,1392,149.3L1440,160L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z'/%3E%3C/svg%3E")`,
          backgroundSize: "cover",
          backgroundPosition: "bottom",
        }}
      />

      <div className="relative z-10 w-full max-w-md px-6">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 rounded-2xl bg-accent/20 flex items-center justify-center mx-auto mb-4 glow-accent">
            <Droplets className="w-8 h-8 text-accent" />
          </div>
          <h1 className="text-2xl font-bold text-foreground tracking-tight">OceanGuard AI</h1>
          <p className="text-sm text-muted-foreground mt-1">Oil Spill Detection System</p>
        </div>

        {/* Login Card */}
        <div className="glass-card p-8">
          <div className="flex items-center gap-2 mb-6">
            <Lock className="w-4 h-4 text-accent" />
            <h2 className="text-sm font-semibold text-foreground uppercase tracking-wider">
              {showRegister ? "Create Account" : "Secure Login"}
            </h2>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg flex items-start gap-2 text-red-400 text-sm">
              <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground font-medium">Email Address</label>
              <div className="relative">
                <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="email"
                  placeholder="operator@coastguard.gov"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="pl-10 bg-background/50 border-border/50"
                  required
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs text-muted-foreground font-medium">Password</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type={showPassword ? "text" : "password"}
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="pl-10 pr-10 bg-background/50 border-border/50"
                  required
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <div className="flex justify-end">
              <button type="button" className="text-xs text-accent hover:text-accent/80 transition-colors">
                Forgot password?
              </button>
            </div>

            <Button
              type="submit"
              className="w-full bg-accent text-accent-foreground hover:bg-accent/90"
              disabled={loading}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-4 h-4 border-2 border-accent-foreground/30 border-t-accent-foreground rounded-full animate-spin" />
                  {showRegister ? "Creating Account..." : "Authenticating..."}
                </span>
              ) : showRegister ? (
                "Create Account"
              ) : (
                "Sign In"
              )}
            </Button>

            {/* <div className="text-center text-xs text-muted-foreground">
              {showRegister ? (
                <>
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setShowRegister(false);
                      setError("");
                      setPassword("");
                    }}
                    className="text-accent hover:text-accent/80 transition-colors font-medium"
                  >
                    Sign In
                  </button>
                </>
              ) : (
                <>
                  Don't have an account?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setShowRegister(true);
                      setError("");
                      setPassword("");
                    }}
                    className="text-accent hover:text-accent/80 transition-colors font-medium"
                  >
                    Create one
                  </button>
                </>
              )}
            </div> */}
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-muted-foreground/60 mt-6">
          🔒 Marine Guardian System — For Authorized Personnel Only
        </p>
      </div>
    </div>
  );
};

export default Login;
