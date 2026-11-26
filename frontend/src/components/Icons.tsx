import type { ReactNode } from 'react';

function Icon({ children, fill = 'none' }: { children: ReactNode; fill?: string }) {
  return <svg className="icon" viewBox="0 0 24 24" width="16" height="16" fill={fill} stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>;
}

export const CompareIcon = () => <Icon><path d="M4 8h14M14 4l4 4-4 4M20 16H6M10 12l-4 4 4 4" /></Icon>;
export const HeartIcon = ({ filled }: { filled?: boolean }) => <Icon fill={filled ? 'currentColor' : 'none'}><path d="M12 20.5 4.2 12.7a5 5 0 0 1 7.1-7.1l.7.7.7-.7a5 5 0 0 1 7.1 7.1z" /></Icon>;
export const SearchIcon = () => <Icon><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></Icon>;
export const BackIcon = () => <Icon><path d="M19 12H5M11 6l-6 6 6 6" /></Icon>;
export const CloseIcon = () => <Icon><path d="M6 6l12 12M18 6 6 18" /></Icon>;
export const ChevronIcon = () => <Icon><path d="M9 6l6 6-6 6" /></Icon>;
