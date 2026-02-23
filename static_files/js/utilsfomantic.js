document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('input[type=text]').forEach( node => node.addEventListener('keypress', e => {
      if(e.keyCode == 13) {
        e.preventDefault();
      }
    }))
  });
function calendar_spanish() {
    let text = {
        days: ['D', 'L', 'M', 'X', 'J', 'V', 'S'],
        months: ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio',
            'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
        ],
        monthsShort: ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep',
            'Oct', 'Nov', 'Dic'
        ],
        today: 'Hoy',
        now: 'Ahora',
    }
    return text
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function exportTableToExcel(tableID, filename = 'export'){
    var downloadLink;
    var dataType = 'application/vnd.ms-excel';
    var tableSelect = document.getElementById(tableID);
    var tableHTML = tableSelect.outerHTML.replace(/ /g, '%20');
    
    // Specify file name
    filename = filename?filename+'.xls':'excel_data.xls';
    
    // Create download link element
    downloadLink = document.createElement("a");
    
    document.body.appendChild(downloadLink);
    
    if(navigator.msSaveOrOpenBlob){
        var blob = new Blob(['\ufeff', tableHTML], {
            type: dataType
        });
        navigator.msSaveOrOpenBlob( blob, filename);
    }else{
        // Create a link to the file
        downloadLink.href = 'data:' + dataType + ', ' + tableHTML;
    
        // Setting the file name
        downloadLink.download = filename;
        
        //triggering the function
        downloadLink.click();
    }
}

function new_message(type,title,message,unique=false) {
    if (unique){
        $('.message').remove()
    }
    $('#message-container').append(
        `<div class="ui ${type} floating message">
        <i class="close icon"></i>
        <div class="header">
            ${title}
        </div>
          ${message}
      </div>`
    )
    $('.message .close')
    .on('click', function () {
        let item = $(this)
            .parent('div.message')
            .transition('fade');
            
        item.remove()
    });
}
function error_message(xhr) {
    let code = xhr.status
    if (code==403) error_description = 'No tienes privilegios suficientes para hacer esto.' 
    else if (code == 404) error_description = 'La url solicitada no existe' 
    else if (code == 500) {
        error_description = 'Ocurrió un error procesando la solicitud, contacta al administrador del sistema' 
        console.log(xhr.responseText)
    }
    $('.message').remove()
    $('#message-container').append(
        `<div class="ui error floating message">
        <i class="close icon"></i>
        <div class="header">
            Ups!
        </div>
          ${error_description}
      </div>`
    )
    $('.message .close')
    .on('click', function () {
        let item = $(this)
            .parent('div.message')
            .transition('fade');
            
        item.remove()
    });
}
$('#principal-submenu .dropdown')
            .dropdown()
        ;
$('.message .close')
    .on('click', function () {
        $(this)
            .closest('.message')
            .transition('fade');
    });

  $(document).ready(function(){
    $(this).click(function(e){
        if(e.button == 0){
              $(".popup").removeClass('transition visible')
        }
    });
    $(this).keydown(function(e){
        if(e.keyCode == 27){
              $(".popup").removeClass('transition visible')
              $('.ui.popup.calendar').css({
                'display':'none',
            })
        }
    });
  })