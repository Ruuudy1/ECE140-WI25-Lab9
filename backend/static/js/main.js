// Global auth handler
document.addEventListener('DOMContentLoaded', () => {
    const publicPaths = ['/', '/login', '/signup'];
    const currentPath = window.location.pathname;
    
    if (!publicPaths.includes(currentPath)) {
        // Check if user is not on public pages
        fetch('/api/check-auth')
            .then(response => {
                if (!response.ok) {
                    window.location.href = '/login';
                }
            })
            .catch(() => {
                window.location.href = '/login';
            });
    }
});