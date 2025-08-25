$(document).ready(function() {
    // Abrir modal al hacer clic en un estudiante
    $('.estudiante-item').click(function(e) {
        e.preventDefault();
        var estudianteId = $(this).data('estudiante-id');

        // Mostrar modal con spinner mientras carga
        $('#estudianteModal').fadeIn(300);

        // Cargar detalles del estudiante via AJAX
        $.ajax({
            url: '/estudiante/detalles/' + estudianteId + '/',
            type: 'GET',
            success: function(response) {
                $('#estudianteDetalles').html(response);
            },
            error: function() {
                $('#estudianteDetalles').html(
                    '<div class="alert alert-danger">Error al cargar los detalles del estudiante.</div>'
                );
            }
        });
    });

    // Cerrar modal con el botón X
    $('#closeModal').click(function() {
        $('#estudianteModal').fadeOut(300);
    });

    // Cerrar modal con el botón Cerrar
    $('#cerrarModal').click(function() {
        $('#estudianteModal').fadeOut(300);
    });

    // Cerrar modal haciendo clic fuera del contenido
    $('#estudianteModal').click(function(e) {
        if ($(e.target).closest('.modal-content').length === 0) {
            $('#estudianteModal').fadeOut(300);
        }
    });
});