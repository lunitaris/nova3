// Router vers les bonnes fonctions en fonction du contexte.

document.addEventListener('DOMContentLoaded', () => {
    const isChat = document.querySelector('.main-header .conversation-info');
    const isAdmin = document.body.classList.contains('admin-layout');

    if (isChat) {
        SymbolicGraphUI.addGraphButton({
            target: '.header-actions',
            context: 'chat',
            buttonText: 'Graph Symbolique de la conv'
        });
    }

});
