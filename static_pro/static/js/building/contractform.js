$(document).ready(function(){
    
    $('form').on('submit',function(){
        var details = $(document).find('.detailrow')
        var total = $('#id_valor').val()
        if (details.length==0){
            $('#alert-title').text('Error')
            $('#alert-data').text('No puedes crear una orden sin items')
            $('#general-right-alert').toggleClass('show').toggleClass('alert-danger')
            $('input[type="submit"]').removeClass('disabled')
            return false;
        }
        else if (total=='0'){
            $('#alert-title').text('Error')
            $('#alert-data').text('El valor de la orden debe ser mayor a 0.')
            $('#general-right-alert').toggleClass('show').toggleClass('alert-danger')
            $('input[type="submit"]').removeClass('disabled')
            return false;
        }
        else{
            
        }
    })
    $('#id_proveedorid').prop('readonly',true)
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
        "language": {
            "url": "//cdn.datatables.net/plug-ins/9dcbecd42ad/i18n/Spanish.json"
        },
        "order": [[ 0, "desc" ]]
    })
    var tablaProveedores = $('#tablaProveedores').DataTable({
        "language": {
            "url": "//cdn.datatables.net/plug-ins/9dcbecd42ad/i18n/Spanish.json"
        }
    })
    $('#tablaReq tbody').on('click', 'tr', function () {
        if ($(this).hasClass('selected')) {
            $(this).removeClass('selected');
        } else {
            tablaReq.$('tr.selected').removeClass('selected');
            $(this).addClass('selected');
        }
        var pos = tablaReq.row('.selected').index();
        var row = tablaReq.row(pos).data();
        var idReq = row[0]
        $(this).removeClass('selected')
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
                $('#id_descripcion_contrato').val(data_req.descripcion)
                $('.obraDetailRow').remove()
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
                            '<button type="button" class="close" disabled onclick="borrarObra($(this))">'+
                                '<span aria-hidden="true">&times;</span>'+
                            '</button>'+
                            "<p class='pl-2 my-1'><strong>Obra: </strong>"+nombreobra+"</p>"+
                            '<div id="rowObra'+tipoobra+'">'+
                            '</div>'+
                            '<button class="btn" type="button" data-toggle="modal" data-target="#modalProductos" data-obra="'+tipoobra+'" disabled>'+
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
                        ' <div class="col-1 pr-0">'+
                            '<div class="row">'+
                                '<div class="col-2 pl-0 pr-1 my-auto">'+
                                    '<button class="btn btn btn-danger btn-sm btn-circle btnremoveline" type="button" ><i class="fas fa-minus" aria-hidden="true" disabled></i></button>'+
                                '</div>'+
                                '<div class="col-10 pr-0">'+
                                    '<input type="text" name="item_obra" class="textinput text-center textInput form-control form-control" required="" id="id_item_obra" value="'+idproducto+'" readonly>'+
                                '</div>'+
                            '</div>'+
                        '</div>'+
                        '<div class="col-5">'+
                            '<input type="text" name="descripcion_item" class="textinput textInput form-control form-control" required="" id="id_descripcion_item" value="'+nombreproducto+'" readonly>'+
                        '</div>'+
                        '<div class="col-1">'+
                            '<input type="text" name="unidad_item" value="'+unid+'" class="text-center textinput textInput form-control form-control" readonly="True" required="" id="id_unidad_item">'+
                        '</div>'+
                        '<div class="col-1 px-1">'+
                            '<input type="number" readonly value="'+cantidad+'" name="cantidad_item" class="numberinput text-center form-control form-control" required="" id="id_cantidad_item">'+
                        '</div>'+
                        '<div class="col-2">'+
                            '<input type="number" name="valor_item" value="0" step="0.01" class="text-center numberinput form-control form-control" required="" id="id_valor_item">'+
                        '</div>'+
                        '<div class="col-2">'+
                            '<input type="text" name="total_item" value="0" step="0.01" class="text-center numberinput form-control form-control" readonly="True" required="" id="id_total_item">'+
                        '</div>'+
                        '<input type="text" name="obraItem" value="'+tipoobra+'" hidden>'+
                        '</div>'
                    row.append(newRow)
                }
                $('#id_req_cruce').val(idReq)
                $('#modalRequisiciones').modal('hide')
                $('#btnAddObra').prop('disabled',true)
                $('#id_valor').val('0')
                calcularPagoEfectivo();
            }
        })
    })
    $('#tablaProveedores tbody').on('click', 'tr', function () {
        if ($(this).hasClass('selected')) {
            $(this).removeClass('selected');
        } else {
            tablaProveedores.$('tr.selected').removeClass('selected');
            $(this).addClass('selected');
        }
        var pos = tablaProveedores.row('.selected').index();
        var row = tablaProveedores.row(pos).data();
        var idproveedor = row[0]
        var nombreproveedor = row[1]
        $('#id_proveedorid').val(idproveedor)
        $('#id_nombreproveedor').val(nombreproveedor)
        $('#modalProveedores').modal('hide')
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
            return;
        }
        $('#modalProductos').modal('hide')
        var obra = $('#obraAsignar').val()
        var row = $('#rowObra'+obra)
        var newRow = '<div class="row py-2 detailrow"> <div class="col-1 pr-0"> <div class="row"> <div class="col-2 pl-0 pr-1 my-auto"> <button class="btn btn btn-danger btn-sm btn-circle btnremoveline" type="button"><i class="fas fa-minus" aria-hidden="true"></i></button></div>'+
        '<div class="col-10 pr-0"> <input type="text" name="item_obra" class="textinput text-center textInput form-control form-control" required="" id="id_item_obra" value="'+idproducto+'" readonly></div></div></div>'+
        '<div class="col-5"> <input type="text" name="descripcion_item" class="textinput textInput form-control form-control" required="" id="id_descripcion_item" value="'+nombreproducto+'" readonly></div>'+
        '<div class="col-1"> <input type="text" name="unidad_item" value="'+unid+'" class="text-center textinput textInput form-control form-control" readonly="True" required="" id="id_unidad_item"></div>'+
        '<div class="col-1 px-1"> <input type="number" name="cantidad_item" step="0.01" class="text-center numberinput form-control form-control" required="" id="id_cantidad_item"></div>'+
        '<div class="col-2"> <input type="number" name="valor_item" value="0" step="0.01" class="text-center numberinput form-control form-control" required="" id="id_valor_item"></div>'+
        '<div class="col-2"> <input type="text" name="total_item" value="0" step="0.01" class="text-center numberinput form-control form-control" readonly="True" required="" id="id_total_item"></div>'+
        '<input type="text" name="obraItem" value="'+obraAsignar+'" hidden>'
        '</div>'
        row.append(newRow)
    });
    $('#btnsearchProv').on('click',function(){
        $('#modalProveedores').modal('show')
    })
    $('#btnAddDetalle').on('click',function(){
        $('#modalProductos').modal('show')
    })
    $('#modalProductos').on('show.bs.modal',function(e){
        var trigger = $(e.relatedTarget)
        var obra = trigger.data('obra')
        $('#obraAsignar').val(obra)
        tablaProductos.ajax.reload()
    })
    $('#detaildiv').on('click','button[type="button"]',function(e){
        $(this).closest('.detailrow').remove()
        totalizarContrato()
    });
    $('#detaildiv').on('change','input[name="cantidad_item"]',function(){
        var cantidad = $(this).val()
        var row = $(this).closest('.detailrow')
        var valor_unit = $(row[0].childNodes[5].lastChild).val()
        var total = $(row[0].childNodes[6].lastChild)
        cantidad = parseFloat(cantidad)
        valor_unit = parseFloat(valor_unit)
        vr_total = cantidad*valor_unit
        total.val(vr_total)
        totalizarContrato()
    })
    $('#detaildiv').on('change','input[name="valor_item"]',function(){
        var valor_unit = $(this).val()
        var row = $(this).closest('.detailrow')
        var cantidad = $(row[0].childNodes[4].lastChild).val()
        var total = $(row[0].childNodes[6].lastChild)
        cantidad = parseFloat(cantidad)
        valor_unit = parseFloat(valor_unit)
        vr_total = cantidad*valor_unit
        vr_total = new Intl.NumberFormat('en-US').format(vr_total)
        total.val(vr_total)
        totalizarContrato()
    });
    $('#id_canje').on('change',function(){
        calcularPagoEfectivo();
    });
    $('#id_anticipo').on('change',function(){
        calcularPagoEfectivo();
    });
    $('#id_aiu').on('change',function(){
        calcularPagoEfectivo();
    });
    $('#id_iva').on('change',function(){
        calcularPagoEfectivo();
    });
    $('#btnAddObra').click(function(){
        $('#modalTipoObra').modal('show')
    });
    $('#id_retenciones').on('change',function(){
        calcularPagoEfectivo();
    });
    $('#id_a').on('change',function(){
        calcularPagoEfectivo();
    });
    $('#id_i').on('change',function(){
        calcularPagoEfectivo();
    });
    $('#id_u').on('change',function(){
        calcularPagoEfectivo();
    });
    $('#selectTipoObra').click(function(){
        $('#modalTipoObra').modal('hide')
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
    })
    function verificarItemExiste(item){
        var exists = false
        var detalle = $('.detailrow').each(function(index){
            var row = $(this)
            var detail_item = $(row[0].childNodes[1].lastChild.lastChild.lastChild).val()
            if (item==detail_item){
                exists = true
            }
        })
        return exists
    }
});
function totalizarContrato(node=6){
    var total = 0
    $('.detailrow').each(function(index){
        var row = $(this)
        var subtotal = $(row[0].childNodes[node].lastChild).val()
        subtotal = parseFloat(subtotal.replace(/,/g, ""))
        total += subtotal
    })
    total = new Intl.NumberFormat('en-US').format(total)
    $('#id_valor').val(total)
    calcularPagoEfectivo();
}
function calcularPagoEfectivo(){
    var subtotal = $('#id_valor').val()
    subtotal = parseFloat(subtotal.replace(/,/g, ""))

    var a = $('#id_a').val()
    a = parseFloat(a)
    var i = $('#id_i').val()
    i = parseFloat(i)
    var u = $('#id_u').val()
    u = parseFloat(u)
    var aiu = a+i+u
    aiu = parseFloat(aiu)
    $('#id_aiu').val(aiu)
    var vr_aiu = parseInt(subtotal*aiu/100)
    $('#id_vr_aiu').val(new Intl.NumberFormat('en-US').format(vr_aiu))

    var iva = $('#id_iva').val()
    iva = parseFloat(iva)
    if (u == 0){
        var vr_iva = parseInt(subtotal*iva/100)
    }
    else{
        var vr_iva = parseInt(subtotal*u*iva/10000)
    }
    $('#id_vr_iva').val(new Intl.NumberFormat('en-US').format(vr_iva)) 
    
    var total_acta = subtotal+vr_aiu+vr_iva
    $('#id_total_acta').val(new Intl.NumberFormat('en-US').format(total_acta))
    
    var canje = $('#id_canje').val()
    canje = parseFloat(canje)
    var vr_canje = parseInt(total_acta*canje/100)
    $('#id_vr_canje').val(new Intl.NumberFormat('en-US').format(vr_canje))
    
    var retencion = $('#id_retenciones').val()
    retencion = parseFloat(retencion)
    vr_retencion = parseInt((subtotal + vr_aiu) * retencion/100)
    $('#id_vr_retenciones').val(new Intl.NumberFormat('en-US').format(vr_retencion))

    var efectivo = total_acta-vr_canje-vr_retencion
    efectivo = new Intl.NumberFormat('en-US').format(efectivo)
    $('#id_pago_efectivo').val(efectivo)

    var anticipo = $('#id_anticipo').val()
    anticipo = parseFloat(anticipo)
    var vr_anticipo = parseInt(total_acta*anticipo/100)
    $('#id_vr_anticipo').val(new Intl.NumberFormat('en-US').format(vr_anticipo))
}
function borrarObra(element){
    element.closest('.obraDetailRow').remove()
    totalizarContrato();
}