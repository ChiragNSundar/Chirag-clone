import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { LayoutDashboard, MessageSquare, Network, User, GraduationCap } from 'lucide-react';
import clsx from 'clsx';

const NavItem = ({ to, icon: Icon, label }: { to: string; icon: React.ElementType; label: string }) => (
    <NavLink
        to={to}
        className={({ isActive }) =>
            clsx(
                "flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200",
                isActive
                    ? "bg-primary text-white shadow-lg shadow-primary/20"
                    : "text-zinc-400 hover:text-white hover:bg-white/10"
            )
        }
    >
        <Icon size={20} />
        <span className="font-medium">{label}</span>
    </NavLink>
);

export const Layout = () => {
    const location = useLocation();

    const getPageTitle = () => {
        switch (location.pathname) {
            case '/': return 'Dashboard';
            case '/chat': return 'Chat';
            case '/memory': return 'Memory Graph';
            case '/profile': return 'About Me';
            default: return 'Dashboard';
        }
    };

    return (
        <div className="flex h-screen w-full bg-background text-white overflow-hidden">
            <aside className="w-64 border-r border-white/10 bg-surface/50 backdrop-blur-xl p-4 flex flex-col gap-6">
                <div className="flex items-center gap-3 px-2">
                    <div className="w-10 h-10 rounded-full bg-gradient-to-tr from-primary to-accent flex items-center justify-center">
                        <span className="text-xl">🤖</span>
                    </div>
                    <div>
                        <h1 className="font-bold text-lg">Chirag Clone</h1>
                        <p className="text-xs text-zinc-500">Digital Twin v2.0</p>
                    </div>
                </div>

                <nav className="flex flex-col gap-2 flex-1">
                    <NavItem to="/" icon={LayoutDashboard} label="Dashboard" />
                    <NavItem to="/chat" icon={MessageSquare} label="Chat" />
                    <NavItem to="/memory" icon={Network} label="Memory Graph" />
                    <NavItem to="/profile" icon={User} label="About Me" />
                    <NavItem to="/training" icon={GraduationCap} label="Training" />
                </nav>

                <div className="p-4 rounded-xl bg-white/5 border border-white/10">
                    <p className="text-xs text-zinc-400 mb-2">System Status</p>
                    <div className="flex items-center gap-2 text-sm text-green-400">
                        <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse"></div>
                        Online
                    </div>
                </div>
            </aside>

            <main className="flex-1 relative overflow-hidden flex flex-col">
                <header className="h-16 border-b border-white/10 flex items-center justify-between px-6 bg-surface/30 backdrop-blur-md z-10">
                    <h2 className="font-semibold text-lg">
                        {getPageTitle()}
                    </h2>
                    <div className="flex items-center gap-4">
                    </div>
                </header>

                <div className="flex-1 overflow-auto relative">
                    <Outlet />
                </div>
            </main>
        </div>
    );
};
