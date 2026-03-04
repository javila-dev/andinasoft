$(document).ready(function(){
    $('form').on('submit',function(){
        $('input[type="submit"]').addClass('disabled')
        $('input[type="submit"]').on('click',function(){
            $(this).prop('disabled',true)
        })
    })
    $('#id_proveedorid').prop('readonly',true)
    var tablaProductos = $('#tablaProductos').DataTable({
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
        var pos = tablaProductos.row('.selected').index();
        var row = tablaProductos.row(pos).data();
        var idproducto = row[0]
        var nombreproducto = row[1]
        var precio = parseFloat(row[4].replace(/\./g,""))
        var unid = row[2]
        var valor_contratado =  row[5].replace(/\./g,"")
        var valor_recibido =  row[6].replace(/\./g,"")
        var valor_max = parseFloat(valor_contratado)-parseFloat(valor_recibido)
        tablaProductos.$('tr.selected').removeClass('selected');
        if (verificarItemExiste(idproducto)){
            $('#alert-title').text('Error')
            $('#alert-data').text('El item que estas intentando agregar ya tiene informacion de recibido en esta acta.')
            $('#modalItemsRecibir').modal('hide')
            $('#general-right-alert').toggleClass('show').toggleClass('alert-danger')
            return;
        }
        $('#modalItemsRecibir').modal('hide')
        var row = $('#detaildiv')
        var newRow = '<div class="row py-2 detailrow"> <div class="col-1 pr-0"> <div class="row"> <div class="col-2 pl-0 pr-1 my-auto"> <button class="btn btn btn-danger btn-sm btn-circle btnremoveline" type="button"><i class="fas fa-minus" aria-hidden="true"></i></button></div>'+
        '<div class="col-10 pr-0"> <input type="text" name="item_obra" class="textinput text-center textInput form-control form-control" required="" id="id_item_obra" value="'+idproducto+'" readonly></div></div></div>'+
        '<div class="col-5"> <input type="text" name="descripcion_item" class="textinput textInput form-control form-control" required="" id="id_descripcion_item" value="'+nombreproducto+'" readonly></div>'+
        '<div class="col-1"> <input type="text" name="unidad_item" value="'+unid+'" class="text-center textinput textInput form-control form-control" readonly="True" required="" id="id_unidad_item"></div>'+
        '<div class="col-1 px-1"> <input step="0.01" type="number" name="cantidad_item" data-toggle="tooltip" data-placement="top" title="El valor maximo a recibir es '+valor_max+'" max="'+valor_max+'" value="0" class="text-center numberinput form-control form-control" required="" id="id_cantidad_item"></div>'+
        '<div class="col-2"> <input type="number" name="valor_item" value="'+precio+'" step="0.01" readonly class="text-center numberinput form-control form-control" required="" id="id_valor_item"></div>'+
        '<div class="col-2"> <input type="text" name="total_item" value="0" step="0.01" class="text-center numberinput form-control form-control" readonly="True" required="" id="id_total_item"></div></div>'
        row.append(newRow)
    });
    $('#btnAddDetalle').on('click',function(){
        $('#modalItemsRecibir').modal('show')
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
        var vr_total = cantidad*valor_unit
        vr_total = new Intl.NumberFormat('en-US').format(vr_total)
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
        var vr_total = cantidad*valor_unit
        vr_total = new Intl.NumberFormat('en-US').format(vr_total)
        total.val(vr_total)
        totalizarContrato()
    });
    $('#id_canje').on('change',function(){
        totalizarContrato()
    });
    $('#id_anticipo').on('change',function(){
        totalizarContrato()
    });
    totalizarContrato()
    function verificarItemExiste(item){
        var exists = false
        var detalle = $('.detailrow').each(function(index){
            var row = $(this)
            var detail_item = $(row[0].childNodes[1].lastChild.childNodes[2].lastChild).val()
            if (item==detail_item){
                exists = true
            }
        })
        return exists
    }
    function totalizarContrato(){
        var total = 0
        $('.detailrow').each(function(index){
            var row = $(this)
            var subtotal = $(row[0].childNodes[6].lastChild).val()
            subtotal = parseFloat(subtotal.replace(/,/g, ""))
            total += subtotal
        })
        total = new Intl.NumberFormat('en-US').format(total)
        $('#id_valor').val(total)
        calcularPagoEfectivo();
    }
});
function calcularPagoEfectivo(){
    var subtotal = $('#id_valor').val()
    subtotal = parseFloat(subtotal.replace(/,/g, ""))

    var aiu = $('#id_aiu').val()
    aiu = parseFloat(aiu)
    var vr_aiu = parseInt(subtotal*aiu/100)
    $('#id_vr_aiu').val(new Intl.NumberFormat('en-US').format(vr_aiu))
    var u = $('#id_u').val()
    u = parseFloat(u)
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

    var anticipo = $('#id_anticipo').val()
    anticipo = parseFloat(anticipo)
    var vr_anticipo = parseInt(total_acta*anticipo/100)
    $('#id_vr_anticipo').val(new Intl.NumberFormat('en-US').format(vr_anticipo))

    var efectivo = total_acta-vr_canje-vr_retencion-vr_anticipo
    efectivo = new Intl.NumberFormat('en-US').format(efectivo)
    $('#id_pago_efectivo').val(efectivo)

    
}