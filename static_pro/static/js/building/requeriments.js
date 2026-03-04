$(document).ready(function(){
    $('#btnAddObra').click(function(){
        $('#modalRequisicion').modal('hide')
        $('#modalTipoObra').modal('show')
    })
    $('#selectTipoObra').click(function(){
        var tipoobra = $('#tipoobramenu').val()
        var exists = $(document).find($('#obra'+tipoobra+'DetailRow'))
       if (exists.length){
            $('#alert-title').text('Error')
            $('#alert-data').text('La obra seleccionada ya esta incluida en este contrato')
            $('#general-right-alert').toggleClass('show').toggleClass('alert-danger')
            return;
       }
        nombreobra = $('#tipoobramenu')[0].selectedOptions[0].text
        $('#controlTipoObra').val(tipoobra)
        var row = $(document).find('.detailrow')
        var newP = "<div class='obraDetailRow border-bottom border-gray' id='obra"+tipoobra+"DetailRow'>"+            
            '<button type="button" class="close" onclick="borrarObra($(this))">'+
                '<span aria-hidden="true">&times;</span>'+
            '</button>'+
            "<p class='pl-2 my-1'><strong>Obra: </strong>"+nombreobra+"</p>"+
            '<div id="rowObra'+tipoobra+'">'+
            '</div>'+
            '<button class="btn" type="button" data-toggle="modal" data-target="#modalProductos" data-obra="'+tipoobra+'">'+
                '<i class="fas fa-plus" aria-hidden="true"></i> Agregar item</button>'+
            "</div>"
        if (row.length==0){
            $('#detaildiv').append(newP)
        }
        else{
            $(newP).insertAfter($('.obraDetailRow').last())
        }
        $('#modalTipoObra').modal('hide')
        $('#modalRequisicion').modal('show')
    })
    $('#modalRequisicion').on('show.bs.modal',function(event){
        var trigger = $(event.relatedTarget)
        var nuevo = trigger.data('new')
        if (nuevo==1){
            $(this).find('.modal-title').text('Crear requisicion')
            $('.obraDetailRow').remove()
            $('#submit-id-btncrear').val('Crear')
            $('#submit-id-btnaprobar').css('display','none')
            $('#submit-id-btncrear').css('display','block')
            $('#id_proyecto').val('')
            $('#id_descripcion').val('')
        }
    });
    $('#modalProductos').on('show.bs.modal',function(e){
        tablaProductos.ajax.reload()
        $('#modalRequisicion').modal('hide')
        var trigger = $(e.relatedTarget)
        var obra = trigger.data('obra')
        $('#obraAsignar').val(obra)
    })
    var tablaProductos = $('#tablaProductos').DataTable({
        "language": {
            "url": "//cdn.datatables.net/plug-ins/9dcbecd42ad/i18n/Spanish.json"
        },
        'ajax':{
            'url':'/buildingcontrol/ajax/productos',
            "dataSrc": "data"
        }
    })
    var tablaReq = $('#tablaReq').DataTable({
        "lengthMenu": [[ 25, 50, -1], [ 25, 50, "Todos"]],
        "order": [[ 0, "desc" ]],
        "language": {
            "url": "//cdn.datatables.net/plug-ins/9dcbecd42ad/i18n/Spanish.json"
        }
    })
    $('#tablaProductos tbody').on('click', 'tr', function () {
        if ($(this).hasClass('selected')) {
            $(this).removeClass('selected');
        } else {
            tablaProductos.$('tr.selected').removeClass('selected');
            $(this).addClass('selected');
        }
        var obraAsignar = $('#obraAsignar').val()
        var pos = tablaProductos.row('.selected').index();
        var row = tablaProductos.row(pos).data();
        var idproducto = row[0]
        var nombreproducto = row[1]
        var unid = row[2]
        $(this).removeClass('selected');
        if (verificarItemExiste(idproducto)){
            $('#alert-title').text('Error')
            $('#alert-data').text('El item que estas intentando agregar ya existe en este contrato.')
            $('#modalProductos').modal('hide')
            $('#general-right-alert').toggleClass('show').toggleClass('alert-danger')
            $('#modalRequisicion').modal('show')
            return;
        }
        $('#modalProductos').modal('hide')
        var obra = $('#obraAsignar').val()
        var row = $('#rowObra'+obra)
        var newRow = '<div class="row py-2 detailrow">'+
            '<div class="col-2">'+
                '<div class="row">'+
                    '<div class="col-2 pl-1 pr-1 my-auto">'+
                        '<button class="btn btn btn-danger btn-sm btn-circle btnremoveline" type="button">'+
                            '<i class="fas fa-minus" aria-hidden="true"></i>'+
                        '</button>'+
                    '</div>'+
                '<div class="col-10 pr-0">'+
                    '<input type="text" name="item_obra" class="textinput text-center textInput form-control form-control" required="" id="id_item_obra" value="'+idproducto+'" readonly>'+
                '</div>'+
            '</div>'+
        '</div>'+
        '<div class="col-6">'+
            '<input type="text" name="descripcion_item" class="textinput textInput form-control form-control" required="" id="id_descripcion_item" value="'+nombreproducto+'" readonly>'+
        '</div>'+
        '<div class="col-2">'+
            '<input type="text" name="unidad_item" value="'+unid+'" class="text-center textinput textInput form-control form-control" readonly="True" required="" id="id_unidad_item">'+
        '</div>'+
        '<div class="col-2 px-1">'+
            '<input type="number" name="cantidad_item" class="text-center numberinput form-control form-control" required="" id="id_cantidad_item">'+
        '</div>'+
        '<input type="text" name="obraItem" value="'+obraAsignar+'" hidden>'+
        '</div>'
        row.append(newRow)
        $('#modalRequisicion').modal('show')
    });
    $('#detaildiv').on('click','button[type="button"]',function(e){
        $(this).closest('.detailrow').remove()
    });
    function verificarItemExiste(item){
        var exists = false
        var detalle = $('.detailrow').each(function(index){
            var row = $(this)
            console.log(row)
            var detail_item = $(row[0].childNodes[1].lastChild.lastChild.lastChild).val()
            if (item==detail_item){
                exists = true
            }
        })
        return exists
    }
});
function borrarObra(element){
    element.closest('.obraDetailRow').remove()
}
function abrirDetalleReq(idReq){
    $('#modalRequisicion').modal('show')
    $('#modalRequisicion').find('.modal-title').text('Detalle requisicion '+idReq)
    $('.obraDetailRow').remove()
    $('#id_idReq').val(idReq)
    $.ajax({
        type: 'GET',
        url: '/buildingcontrol/ajax/requisiciones',
        data:{
            'id_req':idReq
        },
        success: function(response){
            data_req = JSON.parse(response['requisicion'])[0]['fields']
            data_items = JSON.parse(response['items'])
            $('#id_proyecto').val(data_req.proyecto)
            $('#id_descripcion').val(data_req.descripcion)
            if (data_req.estado == 'Pendiente'){
                $('#submit-id-btncrear').val('Modificar')
                $('#submit-id-btnaprobar').css('display','block')
                $('#submit-id-btncrear').css('display','block')
            }
            else{
                $('#submit-id-btnaprobar').css('display','none')
                $('#submit-id-btncrear').css('display','none')
            }

            for (i=0;i<data_items.length;i++){
                var idproducto = data_items[i]['item']
                var nombreproducto = data_items[i]['descripcion']
                var unid = data_items[i]['unidad']
                var cantidad = data_items[i]['cantidad']
                var tipoobra  = data_items[i]['item_obra']
                var nombreobra = data_items[i]['obra']

                var actualObra = $('#obra'+tipoobra+'DetailRow')
                var ObraExists = $(document).find(actualObra)
                if (ObraExists.length==0){
                    var row = $(document).find('.detailrow')
                    var newP = "<div class='obraDetailRow border-bottom border-gray' id='obra"+tipoobra+"DetailRow'>"+
                        '<button type="button" class="close" onclick="borrarObra($(this))">'+
                            '<span aria-hidden="true">&times;</span>'+
                        '</button>'+
                        "<p class='pl-2 my-1'><strong>Obra: </strong>"+nombreobra+"</p>"+
                        '<div id="rowObra'+tipoobra+'">'+
                        '</div>'+
                        '<button class="btn" type="button" data-toggle="modal" data-target="#modalProductos" data-obra="'+tipoobra+'">'+
                            '<i class="fas fa-plus" aria-hidden="true"></i> Agregar item</button>'+
                        "</div>"
                    if ('{{contrato.estado}}'=='Aprobado'){
                        var newP = "<div class='obraDetailRow border-bottom border-gray' id='obra"+tipoobra+"DetailRow'>"+
                        "<p class='pl-2 my-1'><strong>Obra: </strong>"+nombreobra+"</p>"+
                        '<div id="rowObra'+tipoobra+'">'+
                        '</div>'+
                        "</div>"
                    }
                    $('#detaildiv').append(newP)
                }
                var row = $('#rowObra'+tipoobra)
                var newRow = '<div class="row py-2 detailrow">'+
                    ' <div class="col-2">'+
                        '<div class="row">'+
                            '<div class="col-2 pl-1 pr-1 my-auto">'+
                                '<button class="btn btn btn-danger btn-sm btn-circle btnremoveline" type="button" ><i class="fas fa-minus" aria-hidden="true"></i></button>'+
                            '</div>'+
                            '<div class="col-10 pr-0">'+
                                '<input type="text" name="item_obra" class="textinput text-center textInput form-control form-control" required="" id="id_item_obra" value="'+idproducto+'" readonly>'+
                            '</div>'+
                        '</div>'+
                    '</div>'+
                    '<div class="col-6">'+
                        '<input type="text" name="descripcion_item" class="textinput textInput form-control form-control" required="" id="id_descripcion_item" value="'+nombreproducto+'" readonly>'+
                    '</div>'+
                    '<div class="col-2">'+
                        '<input type="text" name="unidad_item" value="'+unid+'" class="text-center textinput textInput form-control form-control" readonly="True" required="" id="id_unidad_item">'+
                    '</div>'+
                    '<div class="col-2 px-1">'+
                        '<input type="number" value="'+cantidad+'" name="cantidad_item" class="numberinput text-center form-control form-control" required="" id="id_cantidad_item">'+
                    '</div>'+
                    '<input type="text" name="obraItem" value="'+tipoobra+'" hidden>'+
                    '</div>'
                row.append(newRow)
            }
        }
    })
}
function getProductos(){
    $.ajax({
        type:'GET',
        url:'/buildingcontrol/ajax/productos',
        data:{},
        success: function(response){
            var data = response['productos']
            console.log(data)
            return data;
        }
    })
}