var mediaqueryList = window.matchMedia("(min-width: 768px)");
    $.ajax({
        type:'GET',
        url:'/ajax_request/sb_pinned',
        data:{
            'minimal':1
        },
        success: function(response){
            var sb_mode = response['sb_status']
            if (sb_mode){
                if(mediaqueryList.matches) {
                    $('#sidebar').toggleClass('minimal');
                    $('#sidebarCollapse').toggleClass('minimal');
                    $('#content').toggleClass('nosidebar');
                    if ($('#sidebar').hasClass('minimal')){
                        $('#btnsidebar').removeClass('fa-arrow-left')
                        $('#btnsidebar').addClass('fa-arrow-right')
                    }
                    else{
                        $('#btnsidebar').removeClass('fa-arrow-right')
                        $('#btnsidebar').addClass('fa-arrow-left')
                    }
                }
            }
        }
    })
$(document).ready(function () {
    $(function () {
        $('[data-toggle="tooltip"]').tooltip()
      })
    RevisarImagenesRotas();
    var mediaqueryList = window.matchMedia("(min-width: 768px)");
    $('.collapsebutton').on('click', function () {
        $('#sidebar').toggleClass('minimal');
        $('#sidebarCollapse').toggleClass('minimal');
        $('#content').toggleClass('nosidebar');
        if ($('#sidebar').hasClass('minimal')){
            var minimal = 1
        }
        else{
            var minimal = 0
        }
        if(mediaqueryList.matches) {
            if ($('#sidebar').hasClass('minimal')){
                $('#btnsidebar').removeClass('fa-arrow-left')
                $('#btnsidebar').addClass('fa-arrow-right')
            }
            else{
                $('#btnsidebar').removeClass('fa-arrow-right')
                $('#btnsidebar').addClass('fa-arrow-left')
            }
        }
        else{
            if ($('#sidebar').hasClass('minimal')){
                $('#btnsidebar').removeClass('fa-arrow-right')
                $('#btnsidebar').addClass('fa-arrow-left')
            }
            else{
                $('#btnsidebar').removeClass('fa-arrow-left')
                $('#btnsidebar').addClass('fa-arrow-right')
            }
        }
        $.ajax({
            type:'GET',
            url:'/ajax_request/sb_pinned',
            data:{
                'pinned':minimal
            },
            success: function(response){
            }
        })
    });
    // Script para sustituir imágenes rotas
    function ImagenOk(img) {
        if (!img.complete) return false;
        if (typeof img.naturalWidth !="«undefined" && img.naturalWidth == 0){
            return false;
        }
        return true;
    }
    function RevisarImagenesRotas() {
        var img = document.getElementById('imgUser')
        var replacementImg = "/media/user_photos/male.png";
        if (!ImagenOk(img)) {
            img.src = replacementImg;
        }}
    
    // ]]>
});