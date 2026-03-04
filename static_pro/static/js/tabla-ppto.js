var functionsPpto=(function (){

    var tablappto=$('#tabla-presupuesto').DataTable({
        'scrollY':        "600px",
        'scrollX':        true,
        'scrollCollapse': true,
        'paging':         false,
        'fixedColumns':   {
            'leftColumns': 2
        },
    initComplete: function () {
    this.api().columns().every( function () {
        var column = this;
        var select = $('<select><option value=""></option></select>')
            .appendTo( $(column.footer()).empty() )
            .on( 'change', function () {
                var val = $.fn.dataTable.util.escapeRegex(
                    $(this).val()
                );

                column
                    .search( val ? '^'+val+'$' : '', true, false )
                    .draw();
            } );

        column.data().unique().sort().each( function ( d, j ) {
            select.append( '<option value="'+d+'">'+d+'</option>' )
        } );
    } );
    },
    "footerCallback": function ( row, data, start, end, display ) {
    var api = this.api(), data;

    // Remove the formatting to get integer data for summation
    var intVal = function ( i ) {
        return i.replace('.',',')
            
    };

    // Total over all pages
    total = api
        .column( 7 )
        .data()
        .reduce( function (a, b) {
            return intVal(a) + intVal(b);
        }, 0 );

    // Update footer
    $( api.column( 7 ).footer() ).html(
        '$'+ total
    );
    }
    });
})