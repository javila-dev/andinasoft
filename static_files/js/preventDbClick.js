$(document).ready(function(){
    $('input:submit').on('click',function(e){
        if($(this).hasClass('disabled')){
            e.preventDefault();
        }
        $(this).addClass('disabled')
    })
  })