import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './components/Dashboard';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <header className="border-b border-slate-800 bg-slate-950/95 backdrop-blur sticky top-0 z-50">
          <div className="max-w-screen-2xl mx-auto flex h-14 items-center px-4 gap-3">
            <span className="text-2xl">🐺</span>
            <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
              Jordan Belfort Bot
            </span>
            <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-xs font-semibold text-emerald-400 ml-1">
              LIVE
            </span>
            <div className="ml-auto text-xs text-slate-500">
              Dashboard v1.0
            </div>
          </div>
        </header>

        <main className="max-w-screen-2xl mx-auto p-4 md:p-6">
          <Routes>
            <Route path="/" element={<Dashboard />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
