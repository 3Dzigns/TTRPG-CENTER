import React from 'react';
import { useLocation } from 'react-router-dom';
import { useThemeStore } from '../stores/themeStore';
import TerminalLayout from './terminal/TerminalLayout';
import LCARSLayout from './lcars/LCARSLayout';

interface LayoutProps {
  children: React.ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  const { theme } = useThemeStore();
  const location = useLocation();

  return theme === 'terminal' ? (
    <TerminalLayout currentPath={location.pathname}>
      {children}
    </TerminalLayout>
  ) : (
    <LCARSLayout currentPath={location.pathname}>
      {children}
    </LCARSLayout>
  );
}